from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select, update

from app.models.hr import Employee, ManagerRelation, Organization, Company
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowInstance,
    WorkflowNodeInstance,
    ApprovalAssignment,
    ApprovalAction,
    Delegation,
)
from app.core.errors import AppException


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowNodeSpec:
    def __init__(
        self,
        node_name: str,
        node_type: str,
        role_or_target: str,
        condition: Optional[str] = None,
    ):
        self.node_name = node_name
        self.node_type = node_type  # AGENT (代理人), MANAGER_DIRECT, MANAGER_L2, MANAGER_L3, ORG_DEPT_HEAD, ORG_DIV_HEAD, GM, HR_WINDOW, FINANCE_WINDOW, LEGAL_WINDOW, SEAL_CUSTODIAN
        self.role_or_target = role_or_target
        self.condition = condition  # DSL: "days>=3", "days>=10", "amount>=5000", "has_advance==true", "needs_seal==true"


# 預設 7 大單據標竿簽核節點規範定義 (Standard Workflow Pipelines)
STANDARD_WORKFLOW_SPECS: Dict[str, List[WorkflowNodeSpec]] = {
    "LEAVE": [
        WorkflowNodeSpec("工作代理人審核", "AGENT", "AGENT"),
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("第二層主管審核 (3天以上)", "MANAGER_L2", "L2_MANAGER", condition="days>=3"),
        WorkflowNodeSpec("第三層主管審核 (10天以上)", "MANAGER_L3", "L3_MANAGER", condition="days>=10"),
        WorkflowNodeSpec("人事窗口核備", "HR_WINDOW", "HR_OFFICER"),
    ],
    "EXPENSE": [
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("第二層主管審核 (>=5000)", "MANAGER_L2", "L2_MANAGER", condition="amount>=5000"),
        WorkflowNodeSpec("第三層主管審核 (>=100000)", "MANAGER_L3", "L3_MANAGER", condition="amount>=100000"),
        WorkflowNodeSpec("會計窗口審核", "FINANCE_WINDOW", "FINANCE_OFFICER"),
    ],
    "PAYMENT": [
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("部級主管審核 (>=5000)", "ORG_DEPT_HEAD", "DEPT_HEAD", condition="amount>=5000"),
        WorkflowNodeSpec("處級主管審核 (>=100000)", "ORG_DIV_HEAD", "DIV_HEAD", condition="amount>=100000"),
        WorkflowNodeSpec("總經理審核 (>=500000)", "GM", "GENERAL_MANAGER", condition="amount>=500000"),
        WorkflowNodeSpec("會計窗口付款", "FINANCE_WINDOW", "FINANCE_OFFICER"),
    ],
    "TRAVEL": [
        WorkflowNodeSpec("工作代理人審核", "AGENT", "AGENT"),
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("會計窗口審核 (有預支款)", "FINANCE_WINDOW", "FINANCE_OFFICER", condition="has_advance==true"),
        WorkflowNodeSpec("人事窗口核備", "HR_WINDOW", "HR_OFFICER"),
    ],
    "TRAVEL_SETTLEMENT": [
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("會計窗口審核", "FINANCE_WINDOW", "FINANCE_OFFICER"),
    ],
    "SEAL": [
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("印鑑保管人執行", "SEAL_CUSTODIAN", "SEAL_CUSTODIAN"),
    ],
    "CONTRACT": [
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("第二層主管審核 (>=5000)", "MANAGER_L2", "L2_MANAGER", condition="amount>=5000"),
        WorkflowNodeSpec("第三層主管審核 (>=100000)", "MANAGER_L3", "L3_MANAGER", condition="amount>=100000"),
        WorkflowNodeSpec("法務窗口審查", "LEGAL_WINDOW", "LEGAL_OFFICER"),
        WorkflowNodeSpec("印鑑保管人執行 (需用印)", "SEAL_CUSTODIAN", "SEAL_CUSTODIAN", condition="needs_seal==true"),
    ],
    "OVERTIME": [
        WorkflowNodeSpec("直屬主管審核", "MANAGER_DIRECT", "DIRECT_MANAGER"),
        WorkflowNodeSpec("人事窗口核對", "HR_WINDOW", "HR_OFFICER"),
    ],
}


class WorkflowResolver:
    """安全簽核條件 DSL 解析器與主管鏈解析器"""

    @staticmethod
    def evaluate_condition(condition: Optional[str], context: Dict[str, Any]) -> bool:
        """
        純安全 DSL 條件比對 (不用 eval)
        支援比較符：>=, <=, ==, >, <
        """
        if not condition:
            return True

        cond = condition.strip().replace(" ", "")

        for op in (">=", "<=", "==", ">", "<"):
            if op in cond:
                key, val = cond.split(op, 1)
                ctx_val = context.get(key)
                if ctx_val is None:
                    return False

                # 數值比較
                if op == ">=":
                    return float(ctx_val) >= float(val)
                elif op == "<=":
                    return float(ctx_val) <= float(val)
                elif op == ">":
                    return float(ctx_val) > float(val)
                elif op == "<":
                    return float(ctx_val) < float(val)
                elif op == "==":
                    # 布林或字串比對
                    return str(ctx_val).lower() == str(val).lower()

        return True

    @staticmethod
    def resolve_approver(
        db: DbSession,
        applicant: Employee,
        node_spec: WorkflowNodeSpec,
        context: Dict[str, Any],
    ) -> str:
        """
        依節點型態解析對應之審核員工 ID：
        1. 代理人 (AGENT)：由 context['agent_employee_id'] 提供
        2. 直屬主管 (DIRECT)：查詢 manager_relations DIRECT
        3. 第二層/第三層主管：沿主管鏈向上回溯
        4. 部/處級主管、總經理、窗口：查詢指定角色或部門主管
        """
        if node_spec.node_type == "AGENT":
            agent_id = context.get("agent_employee_id")
            if not agent_id:
                raise AppException(
                    code="MISSING_APPROVER_BLOCKED",
                    message="未指定工作代理人，流程無法送出",
                    status_code=400,
                )
            return agent_id

        if node_spec.node_type == "MANAGER_DIRECT":
            mgr = WorkflowResolver._get_manager(db, applicant.id, level=1)
            if not mgr:
                raise AppException(
                    code="MISSING_APPROVER_BLOCKED",
                    message=f"員工 [{applicant.full_name}] 查無直屬主管，無法送審，請聯絡人事窗口",
                    status_code=400,
                )
            return mgr.id

        if node_spec.node_type == "MANAGER_L2":
            mgr = WorkflowResolver._get_manager(db, applicant.id, level=2)
            if not mgr:
                raise AppException(
                    code="MISSING_APPROVER_BLOCKED",
                    message=f"員工 [{applicant.full_name}] 查無第二層主管，門檻審核無法推進",
                    status_code=400,
                )
            return mgr.id

        if node_spec.node_type == "MANAGER_L3":
            mgr = WorkflowResolver._get_manager(db, applicant.id, level=3)
            if not mgr:
                raise AppException(
                    code="MISSING_APPROVER_BLOCKED",
                    message=f"員工 [{applicant.full_name}] 查無第三層主管，門檻審核無法推進",
                    status_code=400,
                )
            return mgr.id

        # 窗口或角色指定（人事、會計、法務、保管人、GM）
        target_emp_id = context.get(f"{node_spec.node_type.lower()}_id")
        if target_emp_id:
            return target_emp_id

        # 若 context 提供預設窗口員工 ID
        window_default = context.get("default_window_employee_id")
        if window_default:
            return window_default

        raise AppException(
            code="MISSING_APPROVER_BLOCKED",
            message=f"節點 [{node_spec.node_name}] 查無合法受派主管或窗口員工，系統依規約阻止送審",
            status_code=400,
        )

    @staticmethod
    def _get_manager(db: DbSession, employee_id: str, level: int = 1) -> Optional[Employee]:
        """沿主管鏈回溯指定層級之主管 (Level 1: 直屬, Level 2: 上上一層, Level 3: 上上上一層)"""
        current_emp_id = employee_id
        for _ in range(level):
            stmt = (
                select(ManagerRelation.manager_id)
                .where(
                    ManagerRelation.employee_id == current_emp_id,
                    ManagerRelation.relation_type == "DIRECT",
                    (ManagerRelation.effective_to == None) | (ManagerRelation.effective_to >= date.today()),
                )
            )
            mgr_id = db.execute(stmt).scalar_one_or_none()
            if not mgr_id:
                return None
            current_emp_id = mgr_id

        return db.get(Employee, current_emp_id)


class WorkflowEngine:
    """簽核引擎服務 (Workflow Engine Service)"""

    @staticmethod
    def submit_document(
        db: DbSession,
        company_id: str,
        document_type: str,
        document_id: str,
        applicant_employee_id: str,
        context: Dict[str, Any],
    ) -> WorkflowInstance:
        """
        送審單據 (Submit Document)：
        1. 驗證申請者存在
        2. 取得流程版本並以安全 DSL 解析出有效節點清單
        3. 檢查所有節點受派人，若有缺失立刻阻擋
        4. 建立流程實例與節點快照 (Snapshot)
        5. 啟用第 1 個待簽節點，建立受派待辦 (Assignment)
        """
        applicant = db.get(Employee, applicant_employee_id)
        if not applicant:
            raise AppException(code="APPLICANT_NOT_FOUND", message="找不到申請人資料", status_code=404)

        # 取得流程版本
        wf_def = db.get(WorkflowDefinition, document_type)
        if not wf_def:
            # 自動初始化標準定義
            wf_def = WorkflowDefinition(id=document_type, name=f"{document_type} 流程")
            db.add(wf_def)
            db.commit()

        # 取得最新有效版本
        version_stmt = (
            select(WorkflowVersion)
            .where(WorkflowVersion.definition_id == document_type, WorkflowVersion.is_active == True)
            .order_by(WorkflowVersion.version_num.desc())
        )
        wf_ver = db.execute(version_stmt).scalar_one_or_none()

        if not wf_ver:
            # 建立初始版本 1
            specs = STANDARD_WORKFLOW_SPECS.get(document_type, [])
            nodes_config = [
                {
                    "node_name": s.node_name,
                    "node_type": s.node_type,
                    "role_or_target": s.role_or_target,
                    "condition": s.condition,
                }
                for s in specs
            ]
            wf_ver = WorkflowVersion(
                definition_id=document_type,
                version_num=1,
                nodes_config=nodes_config,
                is_active=True,
            )
            db.add(wf_ver)
            db.commit()
            db.refresh(wf_ver)

        # 解析符合門檻條件的節點清單
        specs = [
            WorkflowNodeSpec(
                n["node_name"],
                n["node_type"],
                n["role_or_target"],
                n.get("condition"),
            )
            for n in wf_ver.nodes_config
        ]

        active_nodes: List[Tuple[WorkflowNodeSpec, str]] = []
        for spec in specs:
            if WorkflowResolver.evaluate_condition(spec.condition, context):
                # 解析受派員工 ID (缺簽核人即刻拋出例外阻擋)
                approver_id = WorkflowResolver.resolve_approver(db, applicant, spec, context)
                active_nodes.append((spec, approver_id))

        if not active_nodes:
            raise AppException(
                code="NO_ACTIVE_NODES",
                message="此單據條件無法匹配出任何簽核節點",
                status_code=400,
            )

        # 建立 WorkflowInstance
        now = utc_now()
        snapshot = {
            "applicant": {
                "id": applicant.id,
                "name": applicant.full_name,
                "org_id": applicant.organization_id,
            },
            "context": context,
            "resolved_pipeline": [
                {"name": s.node_name, "type": s.node_type, "approver_id": a_id}
                for s, a_id in active_nodes
            ],
            "submitted_at_utc": now.isoformat(),
        }

        instance = WorkflowInstance(
            company_id=company_id,
            document_type=document_type,
            document_id=document_id,
            applicant_employee_id=applicant.id,
            workflow_version_id=wf_ver.id,
            status="IN_REVIEW",
            current_node_index=0,
            total_nodes=len(active_nodes),
            snapshot_data=snapshot,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(instance)
        db.commit()
        db.refresh(instance)

        # 建立節點快照與首節點待辦
        for idx, (spec, approver_id) in enumerate(active_nodes):
            node_inst = WorkflowNodeInstance(
                instance_id=instance.id,
                node_index=idx,
                node_name=spec.node_name,
                node_type=spec.node_type,
                status="IN_PROGRESS" if idx == 0 else "PENDING",
            )
            db.add(node_inst)
            db.commit()
            db.refresh(node_inst)

            if idx == 0:
                # 建立首節點待簽受派
                assignment = ApprovalAssignment(
                    node_instance_id=node_inst.id,
                    instance_id=instance.id,
                    assigned_employee_id=approver_id,
                    is_completed=False,
                    assigned_at=now,
                )
                db.add(assignment)
                db.commit()

        return instance

    @staticmethod
    def execute_action(
        db: DbSession,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> WorkflowInstance:
        """
        執行簽核動作 (核准、駁回、退回)：
        1. 檢查受派任務有效性與雙重核決防護
        2. 檢查操作者是否為受派人或授權代理人
        3. 防自簽檢查 (Self-approval Prevention)
        4. 原子推進節點、更新實例狀態機
        """
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到待簽核任務", status_code=404)

        if assignment.is_completed:
            raise AppException(code="DOUBLE_ACTION_PREVENTED", message="該簽核任務已處理完畢，不可重複核決", status_code=409)

        instance = db.get(WorkflowInstance, assignment.instance_id)
        if not instance:
            raise AppException(code="INSTANCE_NOT_FOUND", message="找不到簽核實例", status_code=404)

        # 防自簽檢查 (規約明定：申請人不可自簽)
        if operator_employee_id == instance.applicant_employee_id:
            raise AppException(
                code="SELF_APPROVAL_FORBIDDEN",
                message="申請人不可核准自己送出的申請單據",
                status_code=403,
            )

        # 操作人身分驗證 (受派人本人或有效職務代理人)
        is_assigned = (operator_employee_id == assignment.assigned_employee_id)
        if not is_assigned:
            # 檢查職務代理人
            today = date.today()
            delegation_stmt = select(Delegation).where(
                Delegation.delegator_employee_id == assignment.assigned_employee_id,
                Delegation.delegatee_employee_id == operator_employee_id,
                Delegation.start_date <= today,
                Delegation.end_date >= today,
                Delegation.is_active == True,
            )
            has_delegation = db.execute(delegation_stmt).scalar_one_or_none() is not None
            if not has_delegation:
                raise AppException(
                    code="UNAUTHORIZED_APPROVER",
                    message="您非此簽核節點之受派人或有效職務代理人，無權核決",
                    status_code=403,
                )

        now = utc_now()

        # 記錄簽核動作
        act = ApprovalAction(
            assignment_id=assignment.id,
            operator_employee_id=operator_employee_id,
            action=action.upper(),
            comments=comments,
            client_ip=client_ip,
            executed_at=now,
        )
        db.add(act)

        # 完成目前受派
        assignment.is_completed = True
        assignment.completed_at = now

        # 取得目前節點
        current_node = db.get(WorkflowNodeInstance, assignment.node_instance_id)
        current_node.completed_at = now

        if action.upper() == "REJECT":
            current_node.status = "REJECTED"
            instance.status = "REJECTED"
            instance.completed_at = now
        elif action.upper() == "RETURN":
            current_node.status = "RETURNED"
            instance.status = "RETURNED"
            instance.completed_at = now
        elif action.upper() == "APPROVE":
            current_node.status = "APPROVED"
            next_idx = instance.current_node_index + 1

            if next_idx >= instance.total_nodes:
                # 所有節點全部完成 -> APPROVED
                instance.status = "APPROVED"
                instance.completed_at = now
            else:
                # 推進至下一節點
                instance.current_node_index = next_idx

                # 取得下一個節點實例
                next_node_stmt = select(WorkflowNodeInstance).where(
                    WorkflowNodeInstance.instance_id == instance.id,
                    WorkflowNodeInstance.node_index == next_idx,
                )
                next_node = db.execute(next_node_stmt).scalar_one()
                next_node.status = "IN_PROGRESS"

                # 從 snapshot 取得下一節點受派人
                next_approver_id = instance.snapshot_data["resolved_pipeline"][next_idx]["approver_id"]

                # 建立下一個節點待簽受派
                next_assignment = ApprovalAssignment(
                    node_instance_id=next_node.id,
                    instance_id=instance.id,
                    assigned_employee_id=next_approver_id,
                    is_completed=False,
                    assigned_at=now,
                )
                db.add(next_assignment)

        instance.version += 1
        instance.updated_at = now
        db.commit()
        db.refresh(instance)
        return instance

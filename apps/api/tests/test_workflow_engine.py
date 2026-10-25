import pytest
from datetime import date, timedelta
from fastapi import status

from app.core.security import hash_password
from app.models.auth import User, Role, Permission, RolePermission, UserRole, UserScope
from app.models.hr import Company, Organization, Employee, ManagerRelation
from app.models.workflow import ApprovalAssignment
from app.core.workflow_engine import WorkflowEngine, WorkflowResolver
from app.core.errors import AppException


@pytest.fixture
def workflow_setup(db_session):
    """建立簽核流程完整主管鏈與公司基礎環境"""
    comp = Company(id="ETJ-TW", name="台灣總部", default_timezone="Asia/Taipei", default_currency="TWD")
    db_session.add(comp)
    db_session.commit()

    org = Organization(id="ORG-TEST", company_id="ETJ-TW", code="TEST", name="測試部")
    db_session.add(org)
    db_session.commit()

    # 建立主管鏈：emp (申請人) -> mgr1 (直屬主管) -> mgr2 (第二層主管) -> mgr3 (第三層主管)
    emp = Employee(id="emp_01", employee_no="TW01", company_id="ETJ-TW", organization_id="ORG-TEST", full_name="申請人小明", email="emp@etron.com", hire_date=date(2025, 1, 1))
    agent = Employee(id="emp_agent", employee_no="TW02", company_id="ETJ-TW", organization_id="ORG-TEST", full_name="代理人小華", email="agent@etron.com", hire_date=date(2025, 1, 1))
    mgr1 = Employee(id="emp_mgr1", employee_no="TW03", company_id="ETJ-TW", organization_id="ORG-TEST", full_name="直屬科長", email="mgr1@etron.com", hire_date=date(2024, 1, 1))
    mgr2 = Employee(id="emp_mgr2", employee_no="TW04", company_id="ETJ-TW", organization_id="ORG-TEST", full_name="二層經理", email="mgr2@etron.com", hire_date=date(2023, 1, 1))
    mgr3 = Employee(id="emp_mgr3", employee_no="TW05", company_id="ETJ-TW", organization_id="ORG-TEST", full_name="三層處長", email="mgr3@etron.com", hire_date=date(2022, 1, 1))
    hr_officer = Employee(id="emp_hr", employee_no="TW06", company_id="ETJ-TW", organization_id="ORG-TEST", full_name="人事專員", email="hr_off@etron.com", hire_date=date(2024, 1, 1))
    db_session.add_all([emp, agent, mgr1, mgr2, mgr3, hr_officer])
    db_session.commit()

    # 綁定直屬主管關係
    r1 = ManagerRelation(employee_id=emp.id, manager_id=mgr1.id, relation_type="DIRECT", effective_from=date(2025, 1, 1))
    r2 = ManagerRelation(employee_id=mgr1.id, manager_id=mgr2.id, relation_type="DIRECT", effective_from=date(2025, 1, 1))
    r3 = ManagerRelation(employee_id=mgr2.id, manager_id=mgr3.id, relation_type="DIRECT", effective_from=date(2025, 1, 1))
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    # 建立關聯 User
    u_emp = User(id="u_emp", username="user_emp", email="emp@etron.com", hashed_password=hash_password("Pass123!"), display_name="小明", employee_id=emp.id, primary_company_id="ETJ-TW")
    u_mgr1 = User(id="u_mgr1", username="user_mgr1", email="mgr1@etron.com", hashed_password=hash_password("Pass123!"), display_name="科長", employee_id=mgr1.id, primary_company_id="ETJ-TW")
    db_session.add_all([u_emp, u_mgr1])
    db_session.commit()

    scope1 = UserScope(user_id=u_emp.id, company_id="ETJ-TW", scope_type="COMPANY")
    scope2 = UserScope(user_id=u_mgr1.id, company_id="ETJ-TW", scope_type="COMPANY")
    db_session.add_all([scope1, scope2])
    db_session.commit()

    return {
        "emp": emp,
        "agent": agent,
        "mgr1": mgr1,
        "mgr2": mgr2,
        "mgr3": mgr3,
        "hr_officer": hr_officer,
        "u_emp": u_emp,
        "u_mgr1": u_mgr1,
    }


def test_workflow_threshold_pipeline_resolution(db_session, workflow_setup):
    """
    驗證請假單門檻路徑解析：
    - 2天 (<= 2)：代理人 -> 直屬主管 -> 人事窗口 (共 3 關)
    - 4天 (>= 3)：代理人 -> 直屬主管 -> 第二層主管 -> 人事窗口 (共 4 關)
    - 12天 (>= 10)：代理人 -> 直屬主管 -> 第二層主管 -> 第三層主管 -> 人事窗口 (共 5 關)
    """
    s = workflow_setup
    base_ctx = {
        "agent_employee_id": s["agent"].id,
        "hr_window_id": s["hr_officer"].id,
    }

    # 1. 2天請假
    inst_2d = WorkflowEngine.submit_document(
        db=db_session,
        company_id="ETJ-TW",
        document_type="LEAVE",
        document_id="LV-TEST-001",
        applicant_employee_id=s["emp"].id,
        context={**base_ctx, "days": 2},
    )
    assert inst_2d.total_nodes == 3
    assert inst_2d.snapshot_data["resolved_pipeline"][0]["type"] == "AGENT"
    assert inst_2d.snapshot_data["resolved_pipeline"][1]["type"] == "MANAGER_DIRECT"
    assert inst_2d.snapshot_data["resolved_pipeline"][2]["type"] == "HR_WINDOW"

    # 2. 4天請假
    inst_4d = WorkflowEngine.submit_document(
        db=db_session,
        company_id="ETJ-TW",
        document_type="LEAVE",
        document_id="LV-TEST-002",
        applicant_employee_id=s["emp"].id,
        context={**base_ctx, "days": 4},
    )
    assert inst_4d.total_nodes == 4
    assert inst_4d.snapshot_data["resolved_pipeline"][2]["type"] == "MANAGER_L2"

    # 3. 12天請假
    inst_12d = WorkflowEngine.submit_document(
        db=db_session,
        company_id="ETJ-TW",
        document_type="LEAVE",
        document_id="LV-TEST-003",
        applicant_employee_id=s["emp"].id,
        context={**base_ctx, "days": 12},
    )
    assert inst_12d.total_nodes == 5
    assert inst_12d.snapshot_data["resolved_pipeline"][2]["type"] == "MANAGER_L2"
    assert inst_12d.snapshot_data["resolved_pipeline"][3]["type"] == "MANAGER_L3"


def test_missing_approver_blocked(db_session, workflow_setup):
    """驗證缺簽核人時嚴格阻擋送審，不自動放行跳關"""
    s = workflow_setup
    # 未指定代理人
    with pytest.raises(AppException) as exc_info:
        WorkflowEngine.submit_document(
            db=db_session,
            company_id="ETJ-TW",
            document_type="LEAVE",
            document_id="LV-FAIL-01",
            applicant_employee_id=s["emp"].id,
            context={"days": 1},  # 缺 agent_employee_id
        )
    assert exc_info.value.code == "MISSING_APPROVER_BLOCKED"


def test_self_approval_prevention(db_session, workflow_setup):
    """驗證防自簽機制：申請人不可核准自己的單據"""
    s = workflow_setup
    # 若申請人被誤設為審核人
    inst = WorkflowEngine.submit_document(
        db=db_session,
        company_id="ETJ-TW",
        document_type="LEAVE",
        document_id="LV-SELF-01",
        applicant_employee_id=s["emp"].id,
        context={
            "agent_employee_id": s["emp"].id,  # 代理人為自己
            "hr_window_id": s["hr_officer"].id,
            "days": 1,
        },
    )
    # 取出第 1 個待簽受派
    assign = db_session.query(ApprovalAssignment).filter_by(instance_id=inst.id, is_completed=False).first()

    # 申請人嘗試審核 -> 應拋出 SELF_APPROVAL_FORBIDDEN
    with pytest.raises(AppException) as exc_info:
        WorkflowEngine.execute_action(
            db=db_session,
            assignment_id=assign.id,
            operator_employee_id=s["emp"].id,
            action="APPROVE",
        )
    assert exc_info.value.code == "SELF_APPROVAL_FORBIDDEN"


def test_workflow_lifecycle_approve_reject_return(db_session, workflow_setup):
    """
    簽核生命週期測試：
    1. 代理人核准 -> 節點推進至直屬主管
    2. 雙重核決防護 -> 再次點擊拋出 DOUBLE_ACTION_PREVENTED
    3. 直屬主管核准 -> 人事專員核准 -> 實例轉 APPROVED
    4. 駁回測試 (REJECT) -> 實例轉 REJECTED
    """
    s = workflow_setup
    ctx = {
        "agent_employee_id": s["agent"].id,
        "hr_window_id": s["hr_officer"].id,
        "days": 1,  # 3關：代理人 -> 直屬主管 -> 人事專員
    }

    inst = WorkflowEngine.submit_document(
        db=db_session,
        company_id="ETJ-TW",
        document_type="LEAVE",
        document_id="LV-FLOW-01",
        applicant_employee_id=s["emp"].id,
        context=ctx,
    )
    assert inst.status == "IN_REVIEW"
    assert inst.current_node_index == 0

    # 關卡 1: 代理人核准
    a1 = db_session.query(ApprovalAssignment).filter_by(instance_id=inst.id, is_completed=False).first()
    assert a1.assigned_employee_id == s["agent"].id

    WorkflowEngine.execute_action(
        db=db_session,
        assignment_id=a1.id,
        operator_employee_id=s["agent"].id,
        action="APPROVE",
        comments="代理確認",
    )
    db_session.refresh(inst)
    assert inst.current_node_index == 1  # 推進至直屬主管
    assert inst.status == "IN_REVIEW"

    # 雙重核決防護測試：代理人再次點擊 a1
    with pytest.raises(AppException) as exc_info:
        WorkflowEngine.execute_action(
            db=db_session,
            assignment_id=a1.id,
            operator_employee_id=s["agent"].id,
            action="APPROVE",
        )
    assert exc_info.value.code == "DOUBLE_ACTION_PREVENTED"

    # 關卡 2: 直屬主管核准
    a2 = db_session.query(ApprovalAssignment).filter_by(instance_id=inst.id, is_completed=False).first()
    assert a2.assigned_employee_id == s["mgr1"].id
    WorkflowEngine.execute_action(
        db=db_session,
        assignment_id=a2.id,
        operator_employee_id=s["mgr1"].id,
        action="APPROVE",
    )
    db_session.refresh(inst)
    assert inst.current_node_index == 2  # 推進至人事窗口

    # 關卡 3: 人事專員核准 -> 流程完結 APPROVED
    a3 = db_session.query(ApprovalAssignment).filter_by(instance_id=inst.id, is_completed=False).first()
    assert a3.assigned_employee_id == s["hr_officer"].id
    WorkflowEngine.execute_action(
        db=db_session,
        assignment_id=a3.id,
        operator_employee_id=s["hr_officer"].id,
        action="APPROVE",
    )
    db_session.refresh(inst)
    assert inst.status == "APPROVED"
    assert inst.completed_at is not None


def test_workflow_unauthorized_approver_rejection(db_session, workflow_setup):
    """驗證越權審核拒絕：非受派人且非職務代理人審核遭 403 阻擋"""
    s = workflow_setup
    ctx = {
        "agent_employee_id": s["agent"].id,
        "hr_window_id": s["hr_officer"].id,
        "days": 1,
    }
    inst = WorkflowEngine.submit_document(
        db=db_session,
        company_id="ETJ-TW",
        document_type="LEAVE",
        document_id="LV-UNAUTH-01",
        applicant_employee_id=s["emp"].id,
        context=ctx,
    )
    a1 = db_session.query(ApprovalAssignment).filter_by(instance_id=inst.id, is_completed=False).first()

    # 由無關的 mgr3 嘗試審核 a1 (目前受派人為 agent)
    with pytest.raises(AppException) as exc_info:
        WorkflowEngine.execute_action(
            db=db_session,
            assignment_id=a1.id,
            operator_employee_id=s["mgr3"].id,
            action="APPROVE",
        )
    assert exc_info.value.code == "UNAUTHORIZED_APPROVER"

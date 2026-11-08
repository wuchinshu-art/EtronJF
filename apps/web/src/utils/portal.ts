import { currentUser, hasAnyPermission } from './auth';

/**
 * Portal 模組清單：側邊導覽與 Portal 首頁模組卡片的單一事實來源。
 * 前端可見性僅為 UX；實際授權一律由後端 require_permissions 驗證。
 */
export interface PortalModule {
  key: string;
  icon: string;
  labelKey: string;
  permissions?: string[];
  public?: boolean;
}

export const PORTAL_MODULES: PortalModule[] = [
  { key: 'dashboard', icon: '📊', labelKey: 'nav.dashboard', public: true },
  {
    key: 'hr',
    icon: '👥',
    labelKey: 'nav.hr',
    permissions: ['hr.employee.manage', 'hr.org.manage', 'hr.shift.manage', 'hr.ledger.manage'],
  },
  { key: 'leave', icon: '🌴', labelKey: 'nav.leave', permissions: ['leave.create', 'leave.approve', 'leave.cancel'] },
  { key: 'attendance', icon: '⏱️', labelKey: 'nav.attendance', permissions: ['attendance.punch', 'attendance.manage'] },
  {
    key: 'travel',
    icon: '✈️',
    labelKey: 'nav.travel',
    permissions: ['travel.create', 'travel.approve', 'travel.settle', 'travel.finance'],
  },
  { key: 'expense', icon: '🧾', labelKey: 'nav.expense', permissions: ['expense.create', 'expense.approve'] },
  {
    key: 'seal',
    icon: '🔏',
    labelKey: 'nav.seal',
    permissions: ['seal.request', 'seal.approve', 'seal.execute', 'seal.master'],
  },
  {
    key: 'payment',
    icon: '💵',
    labelKey: 'nav.payment',
    permissions: ['payment.create', 'payment.approve', 'payment.finance', 'vendor.manage'],
  },
  {
    key: 'contract',
    icon: '📜',
    labelKey: 'nav.contract',
    permissions: ['contract.create', 'contract.approve', 'contract.archive'],
  },
  { key: 'users', icon: '🛡️', labelKey: 'nav.users', permissions: ['system.user.manage', 'system.role.manage'] },
];

/** 依目前登入者權限過濾可見模組；未登入僅顯示 public 模組 */
export function visiblePortalModules(modules: PortalModule[] = PORTAL_MODULES): PortalModule[] {
  return modules.filter((m) => {
    if (!currentUser.value) return !!m.public;
    if (!m.permissions || m.permissions.length === 0) return true;
    return hasAnyPermission(m.permissions);
  });
}

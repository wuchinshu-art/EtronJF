import { describe, it, expect, beforeEach } from 'vitest';
import {
  currentUser,
  hasPermission,
  hasAnyPermission,
  hasAllPermissions,
  hasRole,
} from '../src/utils/auth';

describe('RBAC 權限與功能表可見性驗證 (RBAC Permissions & Menu Visibility)', () => {
  beforeEach(() => {
    currentUser.value = null;
  });

  it('未登入使用者應無任何權限，受保護功能表完全不顯示', () => {
    expect(hasPermission('hr.employee.manage')).toBe(false);
    expect(hasPermission('system.user.manage')).toBe(false);
    expect(hasAnyPermission(['hr.employee.manage', 'hr.org.manage'])).toBe(false);
    expect(hasRole('ADMIN')).toBe(false);
  });

  it('ADMIN 系統最高管理員應具備無條件全功能存取授權', () => {
    currentUser.value = {
      id: 'admin_user',
      username: 'admin',
      email: 'admin@etron.com',
      display_name: '最高管理員',
      primary_company_id: 'ETJ-TW',
      active_company_id: 'ETJ-TW',
      is_first_login: false,
      roles: ['ADMIN'],
      permissions: [], // 即使 permissions 陣列為空，ADMIN 角色依然擁有全部權限
      csrf_token: 'dummy_token',
    };

    expect(hasPermission('hr.employee.manage')).toBe(true);
    expect(hasPermission('hr.ledger.manage')).toBe(true);
    expect(hasPermission('hr.shift.manage')).toBe(true);
    expect(hasPermission('hr.org.manage')).toBe(true);
    expect(hasPermission('system.user.manage')).toBe(true);
    expect(hasAnyPermission(['leave.create', 'payment.create'])).toBe(true);
    expect(hasAllPermissions(['seal.request', 'contract.create'])).toBe(true);
    expect(hasRole('ADMIN')).toBe(true);
  });

  it('一般使用者依據角色權限精確顯示或隱藏功能表', () => {
    // 假設某角色僅指派了「人事員工管理 (hr.employee.manage)」
    currentUser.value = {
      id: 'hr_clerk',
      username: 'clerk',
      email: 'clerk@etron.com',
      display_name: '人事專員',
      primary_company_id: 'ETJ-TW',
      active_company_id: 'ETJ-TW',
      is_first_login: false,
      roles: ['GENERAL_USER'],
      permissions: ['hr.employee.manage', 'dashboard.view'],
      csrf_token: 'dummy_token',
    };

    // 人事員工功能表應顯示
    expect(hasPermission('hr.employee.manage')).toBe(true);

    // 未獲授權的人事功能表（假額、班別、組織）應隱藏
    expect(hasPermission('hr.ledger.manage')).toBe(false);
    expect(hasPermission('hr.shift.manage')).toBe(false);
    expect(hasPermission('hr.org.manage')).toBe(false);

    // 系統帳號管理功能表應隱藏
    expect(hasPermission('system.user.manage')).toBe(false);
    expect(hasPermission('system.role.manage')).toBe(false);

    // 人事模組整體選單：因具備 hr.employee.manage，模組側邊欄應可見
    const hrModulePerms = ['hr.employee.manage', 'hr.org.manage', 'hr.shift.manage', 'hr.ledger.manage'];
    expect(hasAnyPermission(hrModulePerms)).toBe(true);

    // 帳號模組整體選單：完全無權限，側邊欄應隱藏
    const userModulePerms = ['system.user.manage', 'system.role.manage'];
    expect(hasAnyPermission(userModulePerms)).toBe(false);
  });

  it('當使用者未獲指派任何人事權限時，人事相關功能表與 Tab 全部隱藏', () => {
    currentUser.value = {
      id: 'general_emp',
      username: 'emp1',
      email: 'emp1@etron.com',
      display_name: '基層同仁',
      primary_company_id: 'ETJ-TW',
      active_company_id: 'ETJ-TW',
      is_first_login: false,
      roles: ['GENERAL_USER'],
      permissions: ['leave.create', 'attendance.punch', 'dashboard.view'],
      csrf_token: 'dummy_token',
    };

    const hrModulePerms = ['hr.employee.manage', 'hr.org.manage', 'hr.shift.manage', 'hr.ledger.manage'];
    expect(hasAnyPermission(hrModulePerms)).toBe(false);
    expect(hasPermission('hr.employee.manage')).toBe(false);
    expect(hasPermission('hr.ledger.manage')).toBe(false);
    expect(hasPermission('hr.shift.manage')).toBe(false);
    expect(hasPermission('hr.org.manage')).toBe(false);
  });
});

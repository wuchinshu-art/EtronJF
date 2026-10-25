import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  currentUser,
  csrfToken,
  isAuthenticated,
  login,
  logout,
  changePassword,
  setFirstTimePassword,
  checkAuth,
} from '../src/utils/auth';

describe('Auth State and Management (前端認證與密碼管理)', () => {
  beforeEach(() => {
    currentUser.value = null;
    csrfToken.value = '';
    vi.restoreAllMocks();
  });

  it('初始狀態應為未登入', () => {
    expect(isAuthenticated.value).toBe(false);
    expect(currentUser.value).toBeNull();
    expect(csrfToken.value).toBe('');
  });

  it('登入成功應保存 CSRF Token 並更新登入狀態', async () => {
    // Mock login endpoint
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(async () => {
        return new Response(
          JSON.stringify({
            status: 'success',
            csrf_token: 'mock_csrf_abc123',
            is_first_login: false,
            active_company_id: 'ETJ-TW',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      })
      // Mock /me endpoint
      .mockImplementationOnce(async () => {
        return new Response(
          JSON.stringify({
            id: 'usr-001',
            username: 'hr_manager',
            email: 'hr@etron.com',
            display_name: '人事經理',
            primary_company_id: 'ETJ-TW',
            active_company_id: 'ETJ-TW',
            is_first_login: false,
            roles: ['HR_ADMIN'],
            permissions: ['hr.employee.manage'],
            csrf_token: 'mock_csrf_abc123',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      });

    await login({ username: 'hr_manager', password: 'AdminSecure123!' });

    expect(isAuthenticated.value).toBe(true);
    expect(currentUser.value?.username).toBe('hr_manager');
    expect(currentUser.value?.display_name).toBe('人事經理');
    expect(csrfToken.value).toBe('mock_csrf_abc123');
  });

  it('登出應清空 currentUser 與 csrfToken', async () => {
    currentUser.value = {
      id: 'usr-001',
      username: 'hr_manager',
      email: 'hr@etron.com',
      display_name: '人事經理',
      primary_company_id: 'ETJ-TW',
      active_company_id: 'ETJ-TW',
      is_first_login: false,
      roles: ['HR_ADMIN'],
      permissions: [],
      csrf_token: 'token_xyz',
    };
    csrfToken.value = 'token_xyz';

    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(async () => {
      return new Response(JSON.stringify({ status: 'success' }), { status: 200 });
    });

    await logout();

    expect(isAuthenticated.value).toBe(false);
    expect(currentUser.value).toBeNull();
    expect(csrfToken.value).toBe('');
  });

  it('變更密碼應正確附帶 CSRF 標頭與 payload', async () => {
    csrfToken.value = 'csrf_header_val';

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(async (_url, options: any) => {
      expect(options.headers['X-CSRF-Token']).toBe('csrf_header_val');
      const body = JSON.parse(options.body);
      expect(body.old_password).toBe('OldPass123!');
      expect(body.new_password).toBe('NewPassSecure456!');
      return new Response(JSON.stringify({ status: 'success' }), { status: 200 });
    });

    await changePassword({
      old_password: 'OldPass123!',
      new_password: 'NewPassSecure456!',
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('首次登入變更密碼應正確呼叫 first-time-password 端點', async () => {
    csrfToken.value = 'csrf_first_time';
    currentUser.value = {
      id: 'usr-new',
      username: 'newbie',
      email: 'newbie@etron.com',
      display_name: '新進同仁',
      primary_company_id: 'ETJ-TW',
      active_company_id: 'ETJ-TW',
      is_first_login: true,
      roles: [],
      permissions: [],
      csrf_token: 'csrf_first_time',
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementationOnce(async (_url, options: any) => {
      expect(options.headers['X-CSRF-Token']).toBe('csrf_first_time');
      const body = JSON.parse(options.body);
      expect(body.new_password).toBe('BrandNewPass789!');
      return new Response(JSON.stringify({ status: 'success' }), { status: 200 });
    });

    await setFirstTimePassword({ new_password: 'BrandNewPass789!' });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(currentUser.value?.is_first_login).toBe(false);
  });

  it('checkAuth 在未登入時回傳 null 並清空資料', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(async () => {
      return new Response(JSON.stringify({ detail: 'Unauthenticated' }), { status: 401 });
    });

    const res = await checkAuth();
    expect(res).toBeNull();
    expect(currentUser.value).toBeNull();
  });
});

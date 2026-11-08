import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import i18next from 'i18next';
import I18NextVue from 'i18next-vue';
import { initI18n } from '../src/locales/i18n';
import { currentUser, type UserProfile } from '../src/utils/auth';
import { visiblePortalModules } from '../src/utils/portal';
import { summarizeUserAgent } from '../src/utils/sessions';
import PortalLoginPage from '../src/components/portal/PortalLoginPage.vue';
import PortalHome from '../src/components/portal/PortalHome.vue';
import MySessionsPanel from '../src/components/portal/MySessionsPanel.vue';

function profile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: 'u1',
    username: 'tw_employee',
    email: 'tw_employee@etron.example',
    display_name: '測試員工',
    primary_company_id: 'ETJ-TW',
    active_company_id: 'ETJ-TW',
    is_first_login: false,
    roles: ['GENERAL_USER'],
    permissions: ['leave.create', 'attendance.punch'],
    csrf_token: 'csrf',
    ...overrides,
  };
}

const mountOpts = { global: { plugins: [[I18NextVue, { i18next }]] as any } };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('Portal 模組可見性 (Portal module visibility)', () => {
  beforeEach(() => {
    currentUser.value = null;
  });

  it('未登入只顯示 public 模組', () => {
    expect(visiblePortalModules().map((m) => m.key)).toEqual(['dashboard']);
  });

  it('一般員工只看到被授權的模組，不含帳號與權限管理', () => {
    currentUser.value = profile();
    const keys = visiblePortalModules().map((m) => m.key);
    expect(keys).toContain('leave');
    expect(keys).toContain('attendance');
    expect(keys).not.toContain('users');
    expect(keys).not.toContain('hr');
    expect(keys).not.toContain('payment');
  });

  it('ADMIN 看到全部模組', () => {
    currentUser.value = profile({ roles: ['ADMIN'], permissions: [] });
    expect(visiblePortalModules().map((m) => m.key)).toContain('users');
    expect(visiblePortalModules().length).toBe(10);
  });
});

describe('Portal 畫面元件 (Portal components)', () => {
  beforeEach(async () => {
    await initI18n();
    await i18next.changeLanguage('zh-TW');
    currentUser.value = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('登入頁空白送出顯示必填訊息，且不預填任何帳號密碼', async () => {
    const wrapper = mount(PortalLoginPage, mountOpts);
    expect((wrapper.get('[data-testid="portal-username"]').element as HTMLInputElement).value).toBe('');
    expect((wrapper.get('[data-testid="portal-password"]').element as HTMLInputElement).value).toBe('');
    await wrapper.get('form').trigger('submit');
    expect(wrapper.get('[data-testid="portal-login-error"]').text()).toBe(i18next.t('portal.required'));
  });

  it('登入失敗顯示後端錯誤訊息', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: 'INVALID_CREDENTIALS', message: '帳號或密碼錯誤' } }, 401),
    );
    vi.stubGlobal('fetch', fetchMock);
    window.fetch = fetchMock as any;

    const wrapper = mount(PortalLoginPage, mountOpts);
    await wrapper.get('[data-testid="portal-username"]').setValue('someone');
    await wrapper.get('[data-testid="portal-password"]').setValue('wrong-password');
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({ method: 'POST' }));
    expect(wrapper.get('[data-testid="portal-login-error"]').text()).toContain('帳號或密碼錯誤');
  });

  it('Portal 首頁依權限顯示模組卡片並發出 open-module', async () => {
    currentUser.value = profile();
    window.fetch = vi.fn().mockResolvedValue(jsonResponse([])) as any;
    const wrapper = mount(PortalHome, { ...mountOpts, props: { timezone: 'Asia/Taipei', company: 'ETJ-TW' } });
    await flushPromises();

    const cards = wrapper.findAll('[data-module]').map((c) => c.attributes('data-module'));
    expect(cards).toEqual(['leave', 'attendance']);
    await wrapper.get('[data-module="leave"]').trigger('click');
    expect(wrapper.emitted('open-module')?.[0]).toEqual(['leave']);
    expect(wrapper.get('[data-testid="portal-profile"]').text()).toContain('tw_employee');
  });

  it('工作階段面板依時區顯示並標示目前裝置', async () => {
    currentUser.value = profile();
    const sessions = [
      {
        id: 's1',
        active_company_id: 'ETJ-TW',
        ip_address: '10.0.0.1',
        user_agent: 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/140.0 Safari/537.36',
        created_at: '2026-11-08T01:00:00Z',
        last_accessed_at: '2026-11-08T02:30:00Z',
        expires_at: '2026-11-09T01:00:00Z',
        idle_expires_at: '2026-11-08T03:00:00Z',
        is_current: true,
      },
      {
        id: 's2',
        active_company_id: 'ETJ-TW',
        ip_address: '10.0.0.2',
        user_agent: '',
        created_at: '2026-11-07T23:00:00Z',
        last_accessed_at: '2026-11-07T23:10:00Z',
        expires_at: '2026-11-08T23:00:00Z',
        idle_expires_at: '2026-11-07T23:40:00Z',
        is_current: false,
      },
    ];
    window.fetch = vi.fn().mockResolvedValue(jsonResponse(sessions)) as any;

    const wrapper = mount(MySessionsPanel, { ...mountOpts, props: { timezone: 'Asia/Tokyo' } });
    await flushPromises();

    const rows = wrapper.findAll('[data-testid="session-row"]');
    expect(rows.length).toBe(2);
    expect(rows[0].text()).toContain('目前裝置');
    expect(rows[0].text()).toContain('Chrome · Windows');
    // 01:00Z → 東京 10:00
    expect(rows[0].text()).toContain('2026-11-08 10:00');
    expect(rows[1].text()).toContain('未知裝置');
    expect(wrapper.find('[data-testid="revoke-others"]').exists()).toBe(true);
  });
});

describe('summarizeUserAgent', () => {
  it('辨識常見瀏覽器與作業系統', () => {
    expect(summarizeUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605 Version/17 Safari/605')).toBe(
      'Safari · macOS',
    );
    expect(summarizeUserAgent('Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0')).toBe(
      'Firefox · Linux',
    );
    expect(summarizeUserAgent('')).toBeNull();
    expect(summarizeUserAgent('testclient')).toBe('testclient');
  });
});

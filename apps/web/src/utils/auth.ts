import { ref, computed } from 'vue';

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  display_name: string;
  primary_company_id: string;
  active_company_id: string;
  is_first_login: boolean;
  roles: string[];
  permissions: string[];
  csrf_token: string;
  employee_id?: string | null;
  employee_no?: string | null;
  department_id?: string | null;
  department_name?: string | null;
  manager_id?: string | null;
  manager_name?: string | null;
  manager_no?: string | null;
}

export const currentUser = ref<UserProfile | null>(null);
export const csrfToken = ref<string>('');
export const isAuthLoading = ref<boolean>(false);
export const showLoginModal = ref<boolean>(false);
export const showChangePasswordModal = ref<boolean>(false);
export const showFirstTimeModal = ref<boolean>(false);

export const isAuthenticated = computed(() => currentUser.value !== null);
export const isFirstLogin = computed(() => currentUser.value?.is_first_login ?? false);

/**
 * 檢查當前登入者是否具備指定權限碼
 * 1. 若使用者具備 ADMIN 最高管理員角色，直接返回 true。
 * 2. 檢驗 currentUser.permissions 清單。
 */
export function hasPermission(permissionCode: string): boolean {
  if (!currentUser.value) return false;
  if (currentUser.value.roles?.includes('ADMIN')) return true;
  return currentUser.value.permissions?.includes(permissionCode) ?? false;
}

/**
 * 檢查當前登入者是否具備給定權限碼中的任一項 (OR 聯集關係)
 */
export function hasAnyPermission(permissionCodes: string[]): boolean {
  if (!currentUser.value) return false;
  if (currentUser.value.roles?.includes('ADMIN')) return true;
  if (!permissionCodes || permissionCodes.length === 0) return true;
  const userPerms = new Set(currentUser.value.permissions || []);
  return permissionCodes.some((code) => userPerms.has(code));
}

/**
 * 檢查當前登入者是否具備給定權限碼中的全部項目 (AND 交集關係)
 */
export function hasAllPermissions(permissionCodes: string[]): boolean {
  if (!currentUser.value) return false;
  if (currentUser.value.roles?.includes('ADMIN')) return true;
  if (!permissionCodes || permissionCodes.length === 0) return true;
  const userPerms = new Set(currentUser.value.permissions || []);
  return permissionCodes.every((code) => userPerms.has(code));
}

/**
 * 檢查當前登入者是否具備指定角色
 */
export function hasRole(roleName: string): boolean {
  if (!currentUser.value) return false;
  return currentUser.value.roles?.includes(roleName) ?? false;
}

export async function checkAuth(): Promise<UserProfile | null> {
  isAuthLoading.value = true;
  try {
    const res = await window.fetch('/api/v1/auth/me');
    if (!res.ok) {
      currentUser.value = null;
      csrfToken.value = '';
      return null;
    }
    const profile: UserProfile = await res.json();
    currentUser.value = profile;
    csrfToken.value = profile.csrf_token;
    if (profile.is_first_login) {
      showFirstTimeModal.value = true;
    }
    return profile;
  } catch {
    currentUser.value = null;
    csrfToken.value = '';
    return null;
  } finally {
    isAuthLoading.value = false;
  }
}

export async function login(payload: {
  username: string;
  password: string;
  company_id?: string;
}): Promise<void> {
  const res = await window.fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error?.message || '登入失敗，請確認帳號與密碼');
  }

  const data = await res.json();
  csrfToken.value = data.csrf_token;
  await checkAuth();
  showLoginModal.value = false;
}

export async function logout(): Promise<void> {
  try {
    await window.fetch('/api/v1/auth/logout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken.value,
      },
    });
  } finally {
    currentUser.value = null;
    csrfToken.value = '';
    showLoginModal.value = true;
  }
}

export async function changePassword(payload: {
  old_password: string;
  new_password: string;
}): Promise<void> {
  const res = await apiFetch('/api/v1/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error?.message || '密碼變更失敗');
  }

  showChangePasswordModal.value = false;
}

export async function setFirstTimePassword(payload: {
  new_password: string;
}): Promise<void> {
  const res = await apiFetch('/api/v1/auth/first-time-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error?.message || '首次密碼設定失敗');
  }

  if (currentUser.value) {
    currentUser.value.is_first_login = false;
  }
  showFirstTimeModal.value = false;
}

/**
 * 統一 API 請求封裝：
 * 1. 自動為 POST / PUT / PATCH / DELETE 注入 X-CSRF-Token。
 * 2. 若尚未取得 CSRF 權杖，自動非同步向 /api/v1/auth/me 刷新取得。
 * 3. 若未授權 (401) 或 CSRF 權杖失效 (403)，自動引導開啟登入彈窗。
 */
export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const method = (init?.method || 'GET').toUpperCase();
  const isMutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);

  // 轉換 Headers 為純物件以提供最佳測試與瀏覽器相容性
  const rawHeaders = init?.headers;
  const headers: Record<string, string> = {};
  if (rawHeaders instanceof Headers) {
    rawHeaders.forEach((val, key) => { headers[key] = val; });
  } else if (Array.isArray(rawHeaders)) {
    rawHeaders.forEach(([k, v]) => { headers[k] = v; });
  } else if (rawHeaders) {
    Object.assign(headers, rawHeaders);
  }

  if (isMutating) {
    // 若尚未取得 csrfToken 且非登入端點，嘗試向 /me 刷新
    const urlStr = typeof input === 'string' ? input : input instanceof URL ? input.toString() : (input as Request).url;
    if (!csrfToken.value && !urlStr.includes('/api/v1/auth/login')) {
      await checkAuth();
    }

    if (csrfToken.value && !headers['X-CSRF-Token']) {
      headers['X-CSRF-Token'] = csrfToken.value;
    }
  }

  const response = await window.fetch(input, {
    ...init,
    headers,
  });

  // 攔截認證過期與權限問題
  if (response.status === 401) {
    currentUser.value = null;
    csrfToken.value = '';
    showLoginModal.value = true;
  } else if (response.status === 403) {
    try {
      const clone = response.clone();
      const data = await clone.json();
      if (data?.error?.code === 'CSRF_VERIFICATION_FAILED') {
        // CSRF Token 不匹配，嘗試刷新一次並跳出登入
        await checkAuth();
        if (!currentUser.value) {
          showLoginModal.value = true;
        }
      }
    } catch {
      // 靜默處理
    }
  }

  return response;
}

// 安裝全域 fetch 攔截器，確保所有原生 fetch 亦自動附帶 X-CSRF-Token
if (typeof window !== 'undefined' && window.fetch) {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const method = (init?.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const rawHeaders = init?.headers;
      const headers: Record<string, string> = {};
      if (rawHeaders instanceof Headers) {
        rawHeaders.forEach((val, key) => { headers[key] = val; });
      } else if (Array.isArray(rawHeaders)) {
        rawHeaders.forEach(([k, v]) => { headers[k] = v; });
      } else if (rawHeaders) {
        Object.assign(headers, rawHeaders);
      }

      const urlStr = typeof input === 'string' ? input : input instanceof URL ? input.toString() : (input as Request).url;
      if (!csrfToken.value && !urlStr.includes('/api/v1/auth/login')) {
        await checkAuth();
      }
      if (csrfToken.value && !headers['X-CSRF-Token']) {
        headers['X-CSRF-Token'] = csrfToken.value;
      }
      init = { ...init, headers };
    }
    return nativeFetch(input, init);
  };
}


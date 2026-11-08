import { apiFetch } from './auth';

/** 後端 /auth/sessions 回應 (時間皆為 UTC ISO-8601) */
export interface SessionInfo {
  id: string;
  active_company_id: string;
  ip_address: string | null;
  user_agent: string;
  created_at: string;
  last_accessed_at: string;
  expires_at: string;
  idle_expires_at: string;
  is_current: boolean;
}

async function parseOrThrow<T>(res: Response, fallbackCode: string): Promise<T> {
  if (!res.ok) {
    let code = fallbackCode;
    try {
      code = (await res.json())?.error?.code || fallbackCode;
    } catch {
      // ignore non-JSON body
    }
    throw new Error(code);
  }
  return res.json() as Promise<T>;
}

export async function fetchMySessions(): Promise<SessionInfo[]> {
  return parseOrThrow(await apiFetch('/api/v1/auth/sessions'), 'SESSION_LOAD_FAILED');
}

export async function revokeMySession(id: string): Promise<{ is_current: boolean }> {
  return parseOrThrow(
    await apiFetch(`/api/v1/auth/sessions/${encodeURIComponent(id)}/revoke`, { method: 'POST' }),
    'SESSION_REVOKE_FAILED',
  );
}

export async function revokeMyOtherSessions(): Promise<{ revoked_count: number }> {
  return parseOrThrow(await apiFetch('/api/v1/auth/sessions/revoke-others', { method: 'POST' }), 'SESSION_REVOKE_FAILED');
}

export async function forceLogoutUser(userId: string): Promise<{ revoked_count: number }> {
  return parseOrThrow(
    await apiFetch(`/api/v1/users/${encodeURIComponent(userId)}/sessions/revoke`, { method: 'POST' }),
    'SESSION_REVOKE_FAILED',
  );
}

/** 將 User-Agent 縮寫為易讀的「瀏覽器 · 作業系統」；無法辨識時回傳 null */
export function summarizeUserAgent(ua: string | null | undefined): string | null {
  if (!ua) return null;
  const browser =
    /Edg\//.test(ua) ? 'Edge'
    : /Chrome\//.test(ua) ? 'Chrome'
    : /Firefox\//.test(ua) ? 'Firefox'
    : /Safari\//.test(ua) ? 'Safari'
    : null;
  const os =
    /Windows/.test(ua) ? 'Windows'
    : /iPhone|iPad/.test(ua) ? 'iOS'
    : /Android/.test(ua) ? 'Android'
    : /Mac OS X/.test(ua) ? 'macOS'
    : /Linux/.test(ua) ? 'Linux'
    : null;
  if (!browser && !os) return ua.slice(0, 40);
  return [browser, os].filter(Boolean).join(' · ');
}

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useTranslation } from 'i18next-vue';
import { formatInTimezone } from '../../utils/time';
import { checkAuth } from '../../utils/auth';
import {
  fetchMySessions,
  revokeMySession,
  revokeMyOtherSessions,
  summarizeUserAgent,
  type SessionInfo,
} from '../../utils/sessions';

const props = defineProps<{ timezone: string }>();
const { t } = useTranslation();

const sessions = ref<SessionInfo[]>([]);
const isLoading = ref(false);
const errorMessage = ref('');
const notice = ref('');

async function load() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    sessions.value = await fetchMySessions();
  } catch {
    errorMessage.value = t('portal.sessions.loadFailed');
  } finally {
    isLoading.value = false;
  }
}

async function revoke(s: SessionInfo) {
  errorMessage.value = '';
  try {
    const res = await revokeMySession(s.id);
    if (res.is_current) {
      // 撤銷目前 session 等同登出：重新檢查狀態以回到登入頁
      await checkAuth();
      return;
    }
    notice.value = t('portal.sessions.revoked', { count: 1 });
    await load();
  } catch {
    errorMessage.value = t('portal.sessions.loadFailed');
  }
}

async function revokeOthers() {
  if (!window.confirm(t('portal.sessions.confirmRevokeOthers'))) return;
  errorMessage.value = '';
  try {
    const res = await revokeMyOtherSessions();
    notice.value = t('portal.sessions.revoked', { count: res.revoked_count });
    await load();
  } catch {
    errorMessage.value = t('portal.sessions.loadFailed');
  }
}

onMounted(load);
defineExpose({ load });
</script>

<template>
  <section class="bg-white rounded-2xl border border-border-main shadow-xs p-5" data-testid="my-sessions">
    <div class="flex flex-wrap items-start justify-between gap-3 mb-4">
      <div>
        <h3 class="text-sm font-bold text-text-main">{{ t('portal.sessions.title') }}</h3>
        <p class="text-xs text-text-muted mt-0.5">{{ t('portal.sessions.subtitle') }}</p>
      </div>
      <div class="flex gap-2">
        <button
          @click="load"
          class="px-3 py-1.5 rounded-lg border border-border-main text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
        >
          {{ t('portal.sessions.refresh') }}
        </button>
        <button
          v-if="sessions.some((s) => !s.is_current)"
          @click="revokeOthers"
          class="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold cursor-pointer"
          data-testid="revoke-others"
        >
          {{ t('portal.sessions.revokeOthers') }}
        </button>
      </div>
    </div>

    <p v-if="notice" class="mb-3 p-2.5 text-xs rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200" role="status">
      {{ notice }}
    </p>
    <p v-if="errorMessage" class="mb-3 p-2.5 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200" role="alert">
      {{ errorMessage }}
    </p>

    <p v-if="isLoading" class="text-xs text-text-muted">{{ t('status.loading') }}</p>
    <p v-else-if="!sessions.length && !errorMessage" class="text-xs text-text-muted">{{ t('portal.sessions.empty') }}</p>

    <ul v-else class="divide-y divide-border-main">
      <li
        v-for="s in sessions"
        :key="s.id"
        class="py-3 flex flex-wrap items-center justify-between gap-3"
        data-testid="session-row"
      >
        <div class="min-w-0 text-xs space-y-0.5">
          <p class="font-semibold text-text-main flex items-center gap-2">
            <span>{{ summarizeUserAgent(s.user_agent) || t('portal.sessions.unknownDevice') }}</span>
            <span
              v-if="s.is_current"
              class="px-1.5 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200 text-[10px] font-medium"
            >
              {{ t('portal.sessions.current') }}
            </span>
          </p>
          <p class="text-text-muted">
            {{ t('portal.sessions.ip') }}: <span class="font-mono">{{ s.ip_address || '-' }}</span>
            · {{ t('portal.sessions.company') }}: <span class="font-mono">{{ s.active_company_id }}</span>
          </p>
          <p class="text-text-muted">
            {{ t('portal.sessions.createdAt') }}: <span class="font-mono">{{ formatInTimezone(s.created_at, props.timezone) }}</span>
            · {{ t('portal.sessions.lastAccessedAt') }}: <span class="font-mono">{{ formatInTimezone(s.last_accessed_at, props.timezone) }}</span>
          </p>
        </div>
        <button
          @click="revoke(s)"
          class="px-3 py-1.5 rounded-lg border border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-semibold cursor-pointer"
        >
          {{ s.is_current ? t('auth.logout') : t('portal.sessions.revoke') }}
        </button>
      </li>
    </ul>
  </section>
</template>

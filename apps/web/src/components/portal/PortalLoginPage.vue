<script setup lang="ts">
import { ref } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { login } from '../../utils/auth';
import { availableCompanies } from '../../utils/companies';

/** Portal 全頁登入：未登入時取代整個應用殼層，不顯示任何業務資料 */
const { t, i18next } = useTranslation();

const username = ref('');
const password = ref('');
const companyId = ref(availableCompanies.value[0]?.id ?? '');
const isLoading = ref(false);
const errorMessage = ref('');

async function handleLogin() {
  if (!username.value.trim() || !password.value) {
    errorMessage.value = t('portal.required');
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  try {
    await login({
      username: username.value.trim(),
      password: password.value,
      company_id: companyId.value || undefined,
    });
    password.value = '';
  } catch (err: unknown) {
    errorMessage.value = err instanceof Error && err.message ? err.message : t('portal.loginFailed');
  } finally {
    isLoading.value = false;
  }
}

async function changeLanguage(event: Event) {
  await i18next.changeLanguage((event.target as HTMLSelectElement).value);
}
</script>

<template>
  <div class="min-h-screen bg-(--color-surface-bg) flex flex-col">
    <header class="flex justify-end px-4 sm:px-8 py-4">
      <label class="flex items-center gap-1.5 text-xs bg-white border border-border-main rounded-md px-2.5 py-1">
        <span class="text-text-muted">🗣️ {{ t('header.language') }}</span>
        <select
          :value="i18next.language"
          @change="changeLanguage"
          class="bg-transparent font-semibold text-text-main focus:outline-hidden cursor-pointer"
          data-testid="portal-language"
        >
          <option value="zh-TW">繁體中文</option>
          <option value="ja-JP">日本語</option>
          <option value="en-US">English</option>
          <option value="zh-CN">简体中文</option>
        </select>
      </label>
    </header>

    <main class="flex-1 flex items-center justify-center px-4 pb-12">
      <div class="w-full max-w-4xl grid md:grid-cols-2 bg-white rounded-2xl shadow-xl border border-border-main overflow-hidden">
        <!-- 品牌區 -->
        <section class="hidden md:flex flex-col justify-between p-10 bg-(--color-primary) text-white">
          <div class="w-12 h-12 rounded-xl bg-white/15 flex items-center justify-center font-bold text-lg">ETJ</div>
          <div class="space-y-3">
            <h1 class="text-2xl font-bold leading-snug">{{ t('portal.loginHeroTitle') }}</h1>
            <p class="text-sm text-white/85 leading-relaxed">{{ t('portal.loginHeroSubtitle') }}</p>
          </div>
          <p class="text-xs text-white/70">{{ t('appName') }}</p>
        </section>

        <!-- 登入表單 -->
        <section class="p-6 sm:p-10">
          <div class="md:hidden flex items-center gap-3 mb-6">
            <div class="w-10 h-10 rounded-xl bg-(--color-primary) text-white font-bold flex items-center justify-center">ETJ</div>
            <p class="text-sm font-semibold text-text-main">{{ t('appName') }}</p>
          </div>
          <h2 class="text-lg font-bold text-text-main">{{ t('auth.loginTitle') }}</h2>
          <p class="text-xs text-text-muted mt-1 mb-6">{{ t('auth.loginSubtitle') }}</p>

          <form @submit.prevent="handleLogin" class="space-y-4" novalidate>
            <div
              v-if="errorMessage"
              role="alert"
              class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200"
              data-testid="portal-login-error"
            >
              {{ errorMessage }}
            </div>

            <FormField :label="t('auth.username')" required>
              <input
                v-model="username"
                type="text"
                autocomplete="username"
                :placeholder="t('auth.usernamePlaceholder')"
                class="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-(--color-primary)"
                data-testid="portal-username"
              />
            </FormField>

            <FormField :label="t('auth.password')" required>
              <input
                v-model="password"
                type="password"
                autocomplete="current-password"
                :placeholder="t('portal.passwordPlaceholder')"
                class="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-(--color-primary)"
                data-testid="portal-password"
              />
            </FormField>

            <FormField :label="t('auth.company')">
              <select
                v-model="companyId"
                class="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-2 focus:ring-(--color-primary) cursor-pointer"
              >
                <option v-for="c in availableCompanies" :key="c.id" :value="c.id">{{ c.name }} ({{ c.id }})</option>
              </select>
            </FormField>

            <button
              type="submit"
              :disabled="isLoading"
              class="w-full py-2.5 rounded-xl bg-(--color-primary) hover:bg-primary-hover text-white text-sm font-bold shadow-md transition disabled:opacity-50 cursor-pointer"
              data-testid="portal-login-submit"
            >
              {{ isLoading ? t('status.loading') : t('auth.login') }}
            </button>
          </form>
        </section>
      </div>
    </main>
  </div>
</template>

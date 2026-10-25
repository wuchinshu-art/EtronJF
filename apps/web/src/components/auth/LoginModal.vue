<script setup lang="ts">
import { ref } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { login, showLoginModal, currentUser } from '../../utils/auth';

const { t } = useTranslation();

const username = ref('hr_manager');
const password = ref('AdminSecure123!');
const companyId = ref('ETJ-TW');
const isLoading = ref(false);
const errorMessage = ref('');

async function handleLogin() {
  if (!username.value || !password.value) {
    errorMessage.value = '請輸入使用者帳號與密碼';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    await login({
      username: username.value,
      password: password.value,
      company_id: companyId.value,
    });
  } catch (err: any) {
    errorMessage.value = err.message || '登入失敗，請確認帳號或密碼';
  } finally {
    isLoading.value = false;
  }
}

function fillDemoAccount(user: string, pass: string) {
  username.value = user;
  password.value = pass;
}
</script>

<template>
  <div
    v-if="showLoginModal"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-fade-in"
  >
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-slate-200 overflow-hidden">
      <!-- 頂端企業標誌與標題 -->
      <div class="p-6 pb-4 bg-linear-to-br from-slate-50 to-slate-100/60 border-b border-slate-200/80">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-xl bg-(--color-primary) flex items-center justify-center text-white font-bold text-base shadow-xs">
              ETJ
            </div>
            <div>
              <h3 class="text-base font-bold text-slate-800 leading-tight">
                {{ t('auth.loginTitle') }}
              </h3>
              <p class="text-xs text-slate-500 mt-0.5">
                {{ t('auth.loginSubtitle') }}
              </p>
            </div>
          </div>
          <button
            v-if="currentUser"
            @click="showLoginModal = false"
            class="text-slate-400 hover:text-slate-600 text-xl leading-none cursor-pointer"
          >
            &times;
          </button>
        </div>
      </div>

      <!-- 表單內容 -->
      <form @submit.prevent="handleLogin" class="p-6 space-y-4">
        <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200 animate-shake">
          ⚠️ {{ errorMessage }}
        </div>

        <FormField :label="t('auth.username')" required>
          <input
            v-model="username"
            type="text"
            required
            :placeholder="t('auth.usernamePlaceholder')"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-medium"
          />
        </FormField>

        <FormField :label="t('auth.password')" required>
          <input
            v-model="password"
            type="password"
            required
            placeholder="請輸入密碼"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
          />
        </FormField>

        <FormField :label="t('auth.company')">
          <select
            v-model="companyId"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer font-medium"
          >
            <option value="ETJ-TW">ETJ 台灣總部 (ETJ-TW)</option>
            <option value="ETJ-JP">ETJ 福岡支社 (ETJ-JP)</option>
          </select>
        </FormField>

        <!-- 快速測試帳號小工具 -->
        <div class="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-[11px] text-slate-600 space-y-1.5">
          <div class="font-semibold text-slate-700 flex items-center">
            <span class="mr-1">💡</span> 快速填入測試帳號：
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              @click="fillDemoAccount('hr_manager', 'AdminSecure123!')"
              class="px-2 py-0.5 rounded bg-white border border-slate-300 hover:border-slate-400 font-mono text-[10px] text-slate-800 transition cursor-pointer"
            >
              人事經理 (hr_manager)
            </button>
            <button
              type="button"
              @click="fillDemoAccount('test_admin', 'AdminSecure123!')"
              class="px-2 py-0.5 rounded bg-white border border-slate-300 hover:border-slate-400 font-mono text-[10px] text-slate-800 transition cursor-pointer"
            >
              系統管理員 (test_admin)
            </button>
          </div>
        </div>

        <div class="pt-2">
          <button
            type="submit"
            :disabled="isLoading"
            class="w-full py-2.5 px-4 rounded-xl bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-bold shadow-md hover:shadow-lg transition-all disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-1.5"
          >
            <span v-if="isLoading" class="animate-spin mr-1.5">⏳</span>
            <span>{{ isLoading ? t('status.loading') : t('auth.login') }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

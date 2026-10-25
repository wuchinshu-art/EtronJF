<script setup lang="ts">
import { ref } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { setFirstTimePassword, showFirstTimeModal, logout } from '../../utils/auth';

const { t } = useTranslation();

const newPassword = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');

async function handleSubmit() {
  if (!newPassword.value || !confirmPassword.value) {
    errorMessage.value = '請填寫新密碼與確認密碼';
    return;
  }

  if (newPassword.value.length < 8) {
    errorMessage.value = t('auth.passwordLengthHint');
    return;
  }

  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = t('auth.passwordMismatch');
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    await setFirstTimePassword({
      new_password: newPassword.value,
    });
  } catch (err: any) {
    errorMessage.value = err.message || '首次密碼設定失敗';
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div
    v-if="showFirstTimeModal"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-md p-4 animate-fade-in"
  >
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-slate-200 overflow-hidden">
      <!-- 標題列 -->
      <div class="p-6 bg-amber-50/80 border-b border-amber-200/60">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center text-xl shadow-xs">
            🛡️
          </div>
          <div>
            <h3 class="text-base font-bold text-slate-800">
              {{ t('auth.firstTimeTitle') }}
            </h3>
            <p class="text-xs text-amber-800 mt-0.5">
              {{ t('auth.firstTimeHint') }}
            </p>
          </div>
        </div>
      </div>

      <!-- 表單 -->
      <form @submit.prevent="handleSubmit" class="p-6 space-y-4">
        <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
          ⚠️ {{ errorMessage }}
        </div>

        <FormField :label="t('auth.newPassword')" required>
          <input
            v-model="newPassword"
            type="password"
            required
            minlength="8"
            placeholder="請設定專屬新密碼 (至少8碼)"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
          />
        </FormField>

        <FormField :label="t('auth.confirmPassword')" required>
          <input
            v-model="confirmPassword"
            type="password"
            required
            minlength="8"
            placeholder="請再次確認新密碼"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
          />
        </FormField>

        <div class="pt-2 flex items-center justify-between">
          <button
            type="button"
            @click="logout"
            class="text-xs text-slate-500 hover:text-slate-800 underline cursor-pointer"
          >
            登出並稍後設定
          </button>
          <button
            type="submit"
            :disabled="isLoading"
            class="px-5 py-2 text-xs font-semibold rounded-lg bg-amber-600 hover:bg-amber-700 text-white shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            {{ isLoading ? t('status.loading') : '確認並啟用帳號' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

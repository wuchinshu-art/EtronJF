<script setup lang="ts">
import { ref } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { changePassword, showChangePasswordModal } from '../../utils/auth';

const { t } = useTranslation();

const oldPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

async function handleSubmit() {
  if (!oldPassword.value || !newPassword.value || !confirmPassword.value) {
    errorMessage.value = '請填寫所有欄位';
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
  successMessage.value = '';

  try {
    await changePassword({
      old_password: oldPassword.value,
      new_password: newPassword.value,
    });
    successMessage.value = t('auth.changePasswordSuccess');
    setTimeout(() => {
      showChangePasswordModal.value = false;
      oldPassword.value = '';
      newPassword.value = '';
      confirmPassword.value = '';
      successMessage.value = '';
    }, 1200);
  } catch (err: any) {
    errorMessage.value = err.message || '密碼變更失敗，請確認舊密碼是否正確';
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <div
    v-if="showChangePasswordModal"
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-fade-in"
  >
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-slate-200 overflow-hidden">
      <!-- 標題列 -->
      <div class="p-6 pb-4 bg-slate-50/80 border-b border-slate-200/80 flex items-center justify-between">
        <div class="flex items-center space-x-2.5">
          <span class="text-xl">🔐</span>
          <h3 class="text-base font-bold text-slate-800">
            {{ t('auth.changePassword') }}
          </h3>
        </div>
        <button
          @click="showChangePasswordModal = false"
          class="text-slate-400 hover:text-slate-600 text-xl leading-none"
        >
          &times;
        </button>
      </div>

      <!-- 表單 -->
      <form @submit.prevent="handleSubmit" class="p-6 space-y-4">
        <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
          ⚠️ {{ errorMessage }}
        </div>
        <div v-if="successMessage" class="p-3 text-xs rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200">
          ✅ {{ successMessage }}
        </div>

        <FormField :label="t('auth.oldPassword')" required>
          <input
            v-model="oldPassword"
            type="password"
            required
            placeholder="請輸入目前密碼"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
          />
        </FormField>

        <FormField :label="t('auth.newPassword')" required>
          <input
            v-model="newPassword"
            type="password"
            required
            minlength="8"
            placeholder="請輸入新密碼 (至少8碼)"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
          />
        </FormField>

        <FormField :label="t('auth.confirmPassword')" required>
          <input
            v-model="confirmPassword"
            type="password"
            required
            minlength="8"
            placeholder="請再次輸入新密碼"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
          />
        </FormField>

        <div class="pt-2 flex justify-end space-x-2">
          <button
            type="button"
            @click="showChangePasswordModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-700 transition"
          >
            {{ t('actions.cancel') }}
          </button>
          <button
            type="submit"
            :disabled="isLoading"
            class="px-5 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs transition disabled:opacity-50"
          >
            {{ isLoading ? t('status.loading') : t('actions.submit') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

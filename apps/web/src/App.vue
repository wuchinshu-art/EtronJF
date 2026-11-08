<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import AppShell from './components/common/AppShell.vue';
import PageHeader from './components/common/PageHeader.vue';
import HrManagementView from './components/hr/HrManagementView.vue';
import LeaveManagementView from './components/leave/LeaveManagementView.vue';
import AttendanceManagementView from './components/attendance/AttendanceManagementView.vue';
import TravelManagementView from './components/travel/TravelManagementView.vue';
import ExpenseManagementView from './components/expense/ExpenseManagementView.vue';
import SealManagementView from './components/seal/SealManagementView.vue';
import PaymentManagementView from './components/payment/PaymentManagementView.vue';
import ContractManagementView from './components/contract/ContractManagementView.vue';
import UserManagementView from './components/users/UserManagementView.vue';
import LoginModal from './components/auth/LoginModal.vue';
import ChangePasswordModal from './components/auth/ChangePasswordModal.vue';
import FirstTimePasswordModal from './components/auth/FirstTimePasswordModal.vue';
import PortalLoginPage from './components/portal/PortalLoginPage.vue';
import PortalHome from './components/portal/PortalHome.vue';
import { TIMEZONES } from './utils/time';
import { checkAuth, currentUser, showLoginModal } from './utils/auth';
import { visiblePortalModules } from './utils/portal';

const { t } = useTranslation();

const activeTimezone = ref<string>(localStorage.getItem('etj_timezone') || TIMEZONES.TAIPEI);
const currentModule = ref<string>('dashboard');
const activeCompany = ref<string>('ETJ-TW');
// 首次確認登入狀態完成前不渲染任何畫面，避免未登入時閃現業務內容
const authChecked = ref(false);

function handleTimezoneChange(tz: string) {
  activeTimezone.value = tz;
}

function handleModuleSelect(mod: string) {
  // 僅允許切換至目前帳號可見的模組 (實際授權仍由後端 API 驗證)
  if (visiblePortalModules().some((m) => m.key === mod)) {
    currentModule.value = mod;
  }
}

// 切換登入者 (登出／重新登入) 時回到 Portal 首頁
watch(
  () => currentUser.value?.id,
  () => {
    currentModule.value = 'dashboard';
  }
);

onMounted(async () => {
  await checkAuth();
  // 未登入時改由全頁 Portal 登入畫面處理，不另開登入彈窗
  showLoginModal.value = false;
  authChecked.value = true;
});
</script>

<template>
  <div v-if="!authChecked" class="min-h-screen flex items-center justify-center bg-(--color-surface-bg) text-sm text-text-muted">
    {{ t('portal.checkingSession') }}
  </div>

  <PortalLoginPage v-else-if="!currentUser" />

  <AppShell
    v-else
    :currentModule="currentModule"
    @change-timezone="handleTimezoneChange"
    @change-company="(comp) => activeCompany = comp"
    @select-module="handleModuleSelect"
  >
    <template #default="{ timezone, company }">
      <!-- HR 模組視圖 -->
      <div v-if="currentModule === 'hr'" class="space-y-6">
        <PageHeader
          :title="t('nav.hr')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.hr') }]"
        >
          <template #actions>
            <span v-if="currentUser" class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              🔒 {{ t('dashboard.loggedInAs', { name: currentUser.display_name, username: currentUser.username }) }}
            </span>
            <button
              v-else
              @click="showLoginModal = true"
              class="px-3 py-1.5 rounded-lg bg-(--color-primary) text-white text-xs font-semibold shadow-xs hover:bg-primary-hover transition cursor-pointer"
            >
              🔑 {{ t('dashboard.loginToManage') }}
            </button>
          </template>
        </PageHeader>

        <HrManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 請假管理模組視圖 -->
      <div v-else-if="currentModule === 'leave'" class="space-y-6">
        <PageHeader
          :title="t('nav.leave')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.leave') }]"
        />
        <LeaveManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 出勤管理模組視圖 -->
      <div v-else-if="currentModule === 'attendance'" class="space-y-6">
        <PageHeader
          :title="t('nav.attendance')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.attendance') }]"
        />
        <AttendanceManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 出差與結報模組視圖 -->
      <div v-else-if="currentModule === 'travel'" class="space-y-6">
        <PageHeader
          :title="t('nav.travel')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.travel') }]"
        />
        <TravelManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 費用報支模組視圖 -->
      <div v-else-if="currentModule === 'expense'" class="space-y-6">
        <PageHeader
          :title="t('nav.expense')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.expense') }]"
        />
        <ExpenseManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 用印申請模組視圖 -->
      <div v-else-if="currentModule === 'seal'" class="space-y-6">
        <PageHeader
          :title="t('nav.seal')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.seal') }]"
        />
        <SealManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 廠商請款模組視圖 -->
      <div v-else-if="currentModule === 'payment'" class="space-y-6">
        <PageHeader
          :title="t('nav.payment')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.payment') }]"
        />
        <PaymentManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 合約系統模組視圖 -->
      <div v-else-if="currentModule === 'contract'" class="space-y-6">
        <PageHeader
          :title="t('nav.contract')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.contract') }]"
        />
        <ContractManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- 帳號與權限設定模組視圖 -->
      <div v-else-if="currentModule === 'users'" class="space-y-6">
        <PageHeader
          :title="t('nav.users')"
          :subtitle="t('dashboard.companyAndTz', { company, tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzShortTokyo') : t('dashboard.tzShortTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.users') }]"
        >
          <template #actions>
            <span v-if="currentUser" class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
              🛡️ {{ t('dashboard.adminActive') }}
            </span>
          </template>
        </PageHeader>
        <UserManagementView :companyId="company" :timezone="timezone" />
      </div>

      <!-- Portal 首頁 (預設) -->
      <PortalHome v-else :timezone="timezone" :company="company" @open-module="handleModuleSelect" />
    </template>
  </AppShell>

  <!-- 全域認證彈窗群 (僅登入後；未登入由 PortalLoginPage 處理) -->
  <template v-if="currentUser">
    <LoginModal />
    <ChangePasswordModal />
    <FirstTimePasswordModal />
  </template>
</template>

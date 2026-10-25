<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useTranslation } from 'i18next-vue';
import AppShell from './components/common/AppShell.vue';
import PageHeader from './components/common/PageHeader.vue';
import FilterBar from './components/common/FilterBar.vue';
import DataTable, { type TableColumn } from './components/common/DataTable.vue';
import StatusBadge from './components/common/StatusBadge.vue';
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
import { formatInTimezone, TIMEZONES } from './utils/time';
import { checkAuth, currentUser, showLoginModal, hasAnyPermission } from './utils/auth';

const { t } = useTranslation();

const activeTimezone = ref<string>(localStorage.getItem('etj_timezone') || TIMEZONES.TAIPEI);
const currentModule = ref<string>('dashboard');
const activeCompany = ref<string>('ETJ-TW');

function handleTimezoneChange(tz: string) {
  activeTimezone.value = tz;
}

function handleModuleSelect(mod: string) {
  currentModule.value = mod;
}

// 響應式表格欄位定義（切換語系時即時動態更新）
const columns = computed<TableColumn[]>(() => [
  { key: 'docNo', label: t('dashboard.columns.docNo'), sortable: true, width: '150px' },
  { key: 'type', label: t('dashboard.columns.type'), sortable: true, width: '120px' },
  { key: 'applicant', label: t('dashboard.columns.applicant'), width: '120px' },
  { key: 'amount', label: t('dashboard.columns.amount'), align: 'right', width: '120px' },
  { key: 'status', label: t('dashboard.columns.status'), align: 'center', width: '110px' },
  { key: 'submittedAt', label: t('dashboard.columns.submittedAt'), width: '180px' },
]);

// 範例資料 (時間存 UTC，顯示依 activeTimezone 轉換，typeKey 用於多語系對照)
const sampleRows = ref([
  {
    id: 1,
    docNo: 'LV-202610-0001',
    typeKey: 'leave',
    applicant: '王大明 (TW0102)',
    amount: '-',
    status: 'approved',
    utcTime: '2026-10-23T01:30:00Z',
  },
  {
    id: 2,
    docNo: 'EX-202610-0042',
    typeKey: 'expense',
    applicant: '佐藤健 (JP0088)',
    amount: '¥ 45,000',
    status: 'in_review',
    utcTime: '2026-10-23T02:15:00Z',
  },
  {
    id: 3,
    docNo: 'TR-202610-0019',
    typeKey: 'travel',
    applicant: '林雅婷 (TW0075)',
    amount: 'NT$ 12,500',
    status: 'submitted',
    utcTime: '2026-10-23T00:45:00Z',
  },
  {
    id: 4,
    docNo: 'SE-202610-0005',
    typeKey: 'seal',
    applicant: '陳冠宇 (TW0033)',
    amount: '-',
    status: 'returned',
    utcTime: '2026-10-22T08:00:00Z',
  },
]);

// 搜尋與分頁狀態 (Search and pagination state)
const searchKeyword = ref('');
const currentPage = ref(1);
const pageSize = ref(10);

function handleSearch(kw: string) {
  searchKeyword.value = kw.trim();
  currentPage.value = 1;
}

function handleReset() {
  searchKeyword.value = '';
  currentPage.value = 1;
}

// 根據關鍵字過濾儀表板列表 (Filter dashboard rows by keyword)
const filteredRows = computed(() => {
  const kw = searchKeyword.value.toLowerCase();
  if (!kw) return sampleRows.value;
  return sampleRows.value.filter((row) => {
    const typeLabel = t(`dashboard.types.${row.typeKey}`).toLowerCase();
    const statusLabel = t(`status.${row.status === 'in_review' ? 'inReview' : row.status}`).toLowerCase();
    return (
      row.docNo.toLowerCase().includes(kw) ||
      row.applicant.toLowerCase().includes(kw) ||
      row.amount.toLowerCase().includes(kw) ||
      typeLabel.includes(kw) ||
      statusLabel.includes(kw)
    );
  });
});

// 分頁資料 (Paginated rows)
const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filteredRows.value.slice(start, start + pageSize.value);
});

onMounted(() => {
  checkAuth();
});
</script>

<template>
  <AppShell
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

      <!-- 儀表板視圖 (預設) -->
      <div v-else class="space-y-6">
        <!-- Page Header -->
        <PageHeader
          :title="t('nav.dashboard')"
          :subtitle="t('dashboard.currentTimezone', { tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzTokyo') : t('dashboard.tzTaipei') })"
          :breadcrumbs="[{ label: t('appName') }, { label: t('nav.dashboard') }]"
        >
          <template #actions>
            <button
              v-if="hasAnyPermission(['system.user.manage', 'system.role.manage'])"
              @click="currentModule = 'users'"
              class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-xs font-semibold text-white shadow-xs transition cursor-pointer"
            >
              🛡️ {{ t('nav.users') }}
            </button>
            <button
              v-if="hasAnyPermission(['hr.employee.manage', 'hr.org.manage', 'hr.shift.manage', 'hr.ledger.manage'])"
              @click="currentModule = 'hr'"
              class="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-xs font-semibold text-white shadow-xs transition cursor-pointer"
            >
              👥 {{ t('dashboard.enterHr') }}
            </button>
          </template>
        </PageHeader>

        <!-- Filter Bar -->
        <FilterBar
          :keywordPlaceholder="t('dashboard.searchPlaceholder')"
          @search="handleSearch"
          @reset="handleReset"
        />

        <!-- Data Table with Timezone Conversion -->
        <DataTable
          :columns="columns"
          :rows="paginatedRows"
          :totalCount="filteredRows.length"
          :currentPage="currentPage"
          :pageSize="pageSize"
          @page-change="(p) => currentPage = p"
        >
          <template #type="{ row }">
            <span>{{ t(`dashboard.types.${row.typeKey}`) }}</span>
          </template>
          <template #status="{ row }">
            <StatusBadge :status="row.status" :label="t(`status.${row.status === 'in_review' ? 'inReview' : row.status}`)" />
          </template>
          <template #submittedAt="{ row }">
            <span class="font-mono text-xs text-slate-700">
              {{ formatInTimezone(row.utcTime, timezone) }}
            </span>
          </template>
        </DataTable>
      </div>
    </template>
  </AppShell>

  <!-- 全域認證彈窗群 -->
  <LoginModal />
  <ChangePasswordModal />
  <FirstTimePasswordModal />
</template>

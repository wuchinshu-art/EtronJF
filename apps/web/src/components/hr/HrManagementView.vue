<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import PersonManagementView from './PersonManagementView.vue';
import OnboardModal from './OnboardModal.vue';
import TransferModal from './TransferModal.vue';
import EmployeeHistoryModal from './EmployeeHistoryModal.vue';
import EmployeeDetailModal from './EmployeeDetailModal.vue';
import CompanyManagement from './CompanyManagement.vue';
import OrgTree from './OrgTree.vue';
import ShiftList from './ShiftList.vue';
import LeaveAdminView from './LeaveAdminView.vue';
import { apiFetch, hasPermission, hasAnyPermission } from '../../utils/auth';

interface EmployeeItem {
  id: string;
  employee_no: string;
  company_id: string;
  organization_id: string;
  full_name: string;
  english_name?: string | null;
  job_title?: string | null;
  job_grade?: string | null;
  email: string;
  mobile_phone?: string | null;
  hire_date: string;
  resign_date: string | null;
  status: string;
  version: number;
  default_shift_id?: string | null;
}

interface ShiftSummary {
  id: string;
  company_id: string;
  code: string;
  name: string;
  work_start_time: string;
  work_end_time: string;
  timezone?: string;
}

interface OrgItem {
  id: string;
  company_id: string;
  code: string;
  name: string;
  level: string;
}

const props = defineProps<{
  companyId: string;
  timezone: string;
}>();

const { t } = useTranslation();

// 權限判定：對應四項標準人事權限
const canViewPersons = computed(() => hasPermission('hr.employee.manage'));
const canViewEmployees = computed(() => hasPermission('hr.employee.manage'));
const canViewCompanies = computed(() => hasAnyPermission(['hr.org.manage', 'hr.employee.manage']));
const canViewOrganizations = computed(() => hasPermission('hr.org.manage'));
const canViewShifts = computed(() => hasPermission('hr.shift.manage'));
const canViewLeaveLedger = computed(() => hasPermission('hr.ledger.manage'));

// 可存取的 Tab 清單
const availableTabs = computed(() => {
  const tabs: ('persons' | 'employees' | 'companies' | 'organizations' | 'shifts' | 'leaveLedger')[] = [];
  if (canViewPersons.value) tabs.push('persons');
  if (canViewEmployees.value) tabs.push('employees');
  if (canViewCompanies.value) tabs.push('companies');
  if (canViewOrganizations.value) tabs.push('organizations');
  if (canViewShifts.value) tabs.push('shifts');
  if (canViewLeaveLedger.value) tabs.push('leaveLedger');
  return tabs;
});

const activeTab = ref<'persons' | 'employees' | 'companies' | 'organizations' | 'shifts' | 'leaveLedger'>('persons');

// 監聽可用 Tabs，若當前 activeTab 無權限則自動切換至第一個可見 Tab
watch(
  availableTabs,
  (tabs) => {
    if (tabs.length > 0 && !tabs.includes(activeTab.value)) {
      activeTab.value = tabs[0];
    }
  },
  { immediate: true }
);

const employees = ref<EmployeeItem[]>([]);
const organizations = ref<OrgItem[]>([]);
const shifts = ref<ShiftSummary[]>([]);
const isLoading = ref(false);

// Modals 控制
const showOnboardModal = ref(false);
const targetPersonForOnboard = ref<any | null>(null);

const showTransferModal = ref(false);
const transferMode = ref<'transfer' | 'resign'>('transfer');
const selectedEmployee = ref<EmployeeItem | null>(null);

const showHistoryModal = ref(false);
const showDetailModal = ref(false);
const selectedEmployeeId = ref<string | null>(null);

async function fetchEmployees() {
  isLoading.value = true;
  try {
    const res = await apiFetch(`/api/v1/hr/employees?company_id=${props.companyId}`);
    if (res.ok) {
      employees.value = await res.json();
    }
  } catch {
    employees.value = [];
  } finally {
    isLoading.value = false;
  }
}

async function fetchOrganizations() {
  try {
    const res = await apiFetch(`/api/v1/hr/organizations?company_id=${props.companyId}`);
    if (res.ok) {
      organizations.value = await res.json();
    }
  } catch {
    organizations.value = [];
  }
}

async function fetchShifts() {
  try {
    const res = await apiFetch(`/api/v1/hr/shifts?company_id=${props.companyId}`);
    if (res.ok) {
      shifts.value = await res.json();
    }
  } catch {
    shifts.value = [];
  }
}

function getShiftName(shiftId?: string | null) {
  if (!shiftId) return '';
  const found = shifts.value.find((s) => s.id === shiftId);
  return found ? `${found.name} (${found.code})` : shiftId;
}

function handleStartOnboard(p: any) {
  targetPersonForOnboard.value = p;
  refreshAll();
  showOnboardModal.value = true;
}

function openOnboardDirectly() {
  targetPersonForOnboard.value = null;
  refreshAll();
  showOnboardModal.value = true;
}

function handleOpenCreatePersonFromOnboard() {
  showOnboardModal.value = false;
  activeTab.value = 'persons';
}

function openDetail(emp: EmployeeItem) {
  selectedEmployeeId.value = emp.id;
  showDetailModal.value = true;
}

function openTransfer(emp: EmployeeItem) {
  selectedEmployee.value = emp;
  transferMode.value = 'transfer';
  refreshAll();
  showTransferModal.value = true;
}

function openResign(emp: EmployeeItem) {
  selectedEmployee.value = emp;
  transferMode.value = 'resign';
  refreshAll();
  showTransferModal.value = true;
}

function openHistory(emp: EmployeeItem) {
  selectedEmployee.value = emp;
  showHistoryModal.value = true;
}

function getOrgName(orgId: string): string {
  const o = organizations.value.find((x) => x.id === orgId);
  return o ? `${o.name} (${o.code})` : orgId;
}

function refreshAll() {
  fetchEmployees();
  fetchOrganizations();
  fetchShifts();
}

watch(
  () => props.companyId,
  () => {
    refreshAll();
  },
  { immediate: true }
);

onMounted(() => {
  refreshAll();
});
</script>

<template>
  <div class="space-y-6">
    <!-- 頂端 Tab 切換導航 -->
    <div v-if="availableTabs.length > 0" class="border-b border-slate-200">
      <nav class="flex space-x-6 text-xs font-semibold" aria-label="Tabs">
        <!-- Tab 0: 人員基本檔案庫 -->
        <button
          v-if="canViewPersons"
          @click="activeTab = 'persons'"
          class="py-3 px-1 border-b-2 transition flex items-center space-x-1.5 cursor-pointer"
          :class="activeTab === 'persons' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          <span>🪪</span>
          <span>{{ t('hr.tabs.persons') }}</span>
          <span class="ml-1 px-1.5 py-0.2 rounded-full bg-indigo-50 text-[10px] text-indigo-700 font-mono">
            {{ t('hr.persons.badge') }}
          </span>
        </button>

        <!-- Tab 1: 在職員工與任職管理 -->
        <button
          v-if="canViewEmployees"
          @click="activeTab = 'employees'"
          class="py-3 px-1 border-b-2 transition flex items-center space-x-1.5 cursor-pointer"
          :class="activeTab === 'employees' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          <span>👥</span>
          <span>{{ t('hr.tabs.employees') }}</span>
          <span class="ml-1 px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] text-slate-600 font-mono">
            {{ employees.length }}
          </span>
        </button>

        <!-- Tab 2: 公司基本資料 -->
        <button
          v-if="canViewCompanies"
          @click="activeTab = 'companies'"
          class="py-3 px-1 border-b-2 transition flex items-center space-x-1.5 cursor-pointer"
          :class="activeTab === 'companies' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          <span>🏢</span>
          <span>{{ t('hr.tabs.companies') }}</span>
        </button>

        <!-- Tab 3: 組織與部門階層 -->
        <button
          v-if="canViewOrganizations"
          @click="activeTab = 'organizations'"
          class="py-3 px-1 border-b-2 transition flex items-center space-x-1.5 cursor-pointer"
          :class="activeTab === 'organizations' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          <span>🌳</span>
          <span>{{ t('hr.tabs.organizations') }}</span>
        </button>

        <!-- Tab 4: 班別與工時 -->
        <button
          v-if="canViewShifts"
          @click="activeTab = 'shifts'"
          class="py-3 px-1 border-b-2 transition flex items-center space-x-1.5 cursor-pointer"
          :class="activeTab === 'shifts' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          <span>⏱️</span>
          <span>{{ t('hr.tabs.shifts') }}</span>
        </button>

        <!-- Tab 5: 假額天數與帳本 -->
        <button
          v-if="canViewLeaveLedger"
          @click="activeTab = 'leaveLedger'"
          class="py-3 px-1 border-b-2 transition flex items-center space-x-1.5 cursor-pointer"
          :class="activeTab === 'leaveLedger' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          <span>🌴</span>
          <span>{{ t('hr.tabs.leaveLedger') }}</span>
        </button>
      </nav>
    </div>

    <!-- 無權限警示 -->
    <div v-else class="bg-white p-12 rounded-xl border border-slate-200 text-center space-y-2">
      <div class="text-3xl">🔒</div>
      <div class="text-sm font-bold text-slate-800">無人事管理功能權限</div>
      <div class="text-xs text-slate-500">您的帳號未被授權人事員工、組織部門、班別排班或假額帳本管理權限。</div>
    </div>

    <!-- Tab 0: 人員基本檔案庫 (第 1 步：自然人基本資料維護) -->
    <div v-if="activeTab === 'persons'">
      <PersonManagementView
        @start-onboard="handleStartOnboard"
      />
    </div>

    <!-- Tab 1: 在職員工與任職管理 (第 2 步到第 4 步：報到/異動/離職) -->
    <div v-else-if="activeTab === 'employees'" class="space-y-4">
      <!-- 生命週期指引橫幅 -->
      <div class="p-3.5 bg-linear-to-r from-blue-50/70 via-indigo-50/50 to-slate-50 rounded-xl border border-blue-100 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center space-x-2 text-xs">
          <span class="font-bold text-slate-800">{{ t('hr.lifecycle.bannerTitle') }}</span>
          <div class="flex items-center space-x-1.5 text-slate-600 font-medium">
            <span class="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 shadow-2xs">{{ t('hr.lifecycle.step1') }}</span>
            <span>➔</span>
            <span class="px-2 py-0.5 rounded bg-blue-100/70 border border-blue-300 text-blue-800 font-semibold shadow-2xs">{{ t('hr.lifecycle.step2') }}</span>
            <span>➔</span>
            <span class="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 shadow-2xs">{{ t('hr.lifecycle.step3') }}</span>
            <span>➔</span>
            <span class="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 shadow-2xs">{{ t('hr.lifecycle.step4') }}</span>
          </div>
        </div>
        <div class="text-[11px] text-slate-500">
          {{ t('hr.lifecycle.multiCompanyNote') }}
        </div>
      </div>

      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">{{ t('hr.lifecycle.sectionTitle') }}</h3>
          <p class="text-xs text-text-muted">{{ t('hr.lifecycle.sectionSubtitle') }}</p>
        </div>
        <button
          @click="openOnboardDirectly"
          class="px-3.5 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer flex items-center space-x-1.5"
        >
          <span>➕</span>
          <span>{{ t('hr.lifecycle.startOnboardBtn') }}</span>
        </button>
      </div>

      <!-- 員工表格 -->
      <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-700">
            <thead class="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase border-b border-slate-200">
              <tr>
                <th class="px-4 py-3">{{ t('hr.employee.no') }}</th>
                <th class="px-4 py-3">{{ t('hr.employee.name') }}</th>
                <th class="px-4 py-3">{{ t('hr.employee.jobTitle') }}</th>
                <th class="px-4 py-3">{{ t('hr.employee.dept') }}</th>
                <th class="px-4 py-3">{{ t('hr.employee.email') }}</th>
                <th class="px-4 py-3">{{ t('hr.employee.hireDate') }}</th>
                <th class="px-4 py-3 text-center">{{ t('hr.employee.status') }}</th>
                <th class="px-4 py-3 text-right">{{ t('hr.lifecycle.actionsColumn') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-if="employees.length === 0">
                <td colspan="8" class="px-4 py-8 text-center text-slate-400">{{ t('hr.lifecycle.noEmployees') }}</td>
              </tr>
              <tr v-for="emp in employees" :key="emp.id" class="hover:bg-slate-50/50">
                <td class="px-4 py-3 font-mono font-bold text-slate-900">{{ emp.employee_no }}</td>
                <td class="px-4 py-3">
                  <div class="font-medium text-slate-900">{{ emp.full_name }}</div>
                  <div v-if="emp.english_name" class="text-[11px] text-slate-400">{{ emp.english_name }}</div>
                </td>
                <td class="px-4 py-3 text-slate-700">
                  <span class="font-medium">{{ emp.job_title || '-' }}</span>
                  <span v-if="emp.job_grade" class="ml-1 text-[10px] text-slate-400 font-mono">({{ emp.job_grade }})</span>
                </td>
                <td class="px-4 py-3">
                  <div class="font-medium text-slate-800">{{ getOrgName(emp.organization_id) }}</div>
                  <div v-if="emp.default_shift_id" class="text-[10px] text-sky-700 bg-sky-50 px-1.5 py-0.5 rounded border border-sky-200 inline-flex items-center space-x-1 mt-0.5">
                    <span>⏱️</span>
                    <span>{{ getShiftName(emp.default_shift_id) }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 font-mono text-[11px] text-slate-600">{{ emp.email }}</td>
                <td class="px-4 py-3 font-mono text-slate-600">{{ emp.hire_date }}</td>
                <td class="px-4 py-3 text-center">
                  <span
                    class="px-2 py-0.5 rounded text-[10px] font-semibold"
                    :class="{
                      'bg-emerald-50 text-emerald-700 border border-emerald-200': emp.status === 'ACTIVE',
                      'bg-rose-50 text-rose-700 border border-rose-200': emp.status === 'RESIGNED',
                      'bg-amber-50 text-amber-700 border border-amber-200': emp.status === 'ON_LEAVE',
                    }"
                  >
                    {{ emp.status === 'ACTIVE' ? t('hr.employee.active') : emp.status === 'RESIGNED' ? t('hr.employee.resigned') : t('hr.employee.onLeave') }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right space-x-1.5 whitespace-nowrap">
                  <button
                    @click="openDetail(emp)"
                    class="px-2 py-1 text-[11px] font-medium rounded border border-slate-200 bg-white hover:bg-slate-50 text-blue-600 cursor-pointer inline-flex items-center space-x-1"
                    :title="t('hr.employee.detailBtn')"
                  >
                    <span>🔍</span>
                    <span>{{ t('hr.employee.detailBtn') }}</span>
                  </button>
                  <button
                    v-if="emp.status === 'ACTIVE'"
                    @click="openTransfer(emp)"
                    class="px-2 py-1 text-[11px] font-medium rounded border border-indigo-200 bg-indigo-50/50 hover:bg-indigo-100 text-indigo-700 cursor-pointer inline-flex items-center space-x-1"
                    :title="t('hr.lifecycle.transferBtn')"
                  >
                    <span>🔄</span>
                    <span>{{ t('hr.lifecycle.transferBtn') }}</span>
                  </button>
                  <button
                    v-if="emp.status === 'ACTIVE'"
                    @click="openResign(emp)"
                    class="px-2 py-1 text-[11px] font-medium rounded border border-rose-200 bg-rose-50/50 hover:bg-rose-100 text-rose-700 cursor-pointer inline-flex items-center space-x-1"
                    :title="t('hr.lifecycle.resignBtn')"
                  >
                    <span>🚪</span>
                    <span>{{ t('hr.lifecycle.resignBtn') }}</span>
                  </button>
                  <button
                    @click="openHistory(emp)"
                    class="px-2 py-1 text-[11px] font-medium rounded border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 cursor-pointer inline-flex items-center space-x-1"
                    :title="t('hr.lifecycle.historyBtn')"
                  >
                    <span>📜</span>
                    <span>{{ t('hr.lifecycle.historyBtn') }}</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab 2: 公司基本資料維護 -->
    <div v-else-if="activeTab === 'companies'">
      <CompanyManagement @updated="refreshAll" />
    </div>

    <!-- Tab 3: 組織與部門階層 -->
    <div v-else-if="activeTab === 'organizations'">
      <OrgTree :companyId="props.companyId" />
    </div>

    <!-- Tab 4: 班別與工時 -->
    <div v-else-if="activeTab === 'shifts'">
      <ShiftList :companyId="props.companyId" :timezone="props.timezone" />
    </div>

    <!-- Tab 5: 假額天數與帳本 (假管理) -->
    <div v-else-if="activeTab === 'leaveLedger'">
      <LeaveAdminView :companyId="props.companyId" :employees="employees" />
    </div>

    <!-- 報到 Modal (第 2 步：專注任職設定) -->
    <OnboardModal
      :isOpen="showOnboardModal"
      :companyId="props.companyId"
      :organizations="organizations"
      :shifts="shifts"
      :targetPerson="targetPersonForOnboard"
      @close="showOnboardModal = false"
      @success="refreshAll"
      @open-create-person="handleOpenCreatePersonFromOnboard"
    />

    <!-- 詳情 / 編輯 Modal -->
    <EmployeeDetailModal
      :isOpen="showDetailModal"
      :employeeId="selectedEmployeeId"
      @close="showDetailModal = false"
      @updated="refreshAll"
    />

    <!-- 異動作業 / 離職作業 Modal (第 3、4 步) -->
    <TransferModal
      :isOpen="showTransferModal"
      :mode="transferMode"
      :employee="selectedEmployee"
      :organizations="organizations"
      :shifts="shifts"
      @close="showTransferModal = false"
      @success="refreshAll"
    />

    <!-- 異動歷程 Modal -->
    <EmployeeHistoryModal
      :isOpen="showHistoryModal"
      :employee="selectedEmployee"
      @close="showHistoryModal = false"
    />
  </div>
</template>


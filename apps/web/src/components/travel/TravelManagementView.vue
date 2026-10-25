<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import StatusBadge from '../common/StatusBadge.vue';
import { apiFetch, currentUser } from '../../utils/auth';

const props = defineProps<{
  companyId: string;
  timezone: string;
}>();

const { t } = useTranslation();

interface TravelRequestItem {
  id: string;
  company_id: string;
  employee_id: string;
  request_number: string;
  title: string;
  destination: string;
  start_date: string;
  end_date: string;
  transport_mode: string;
  purpose: string;
  has_advance: boolean;
  advance_currency: string;
  advance_amount: number;
  status: string;
  created_at: string;
}

interface TravelSettlementItem {
  id: string;
  settlement_number: string;
  travel_request_id: string;
  currency: string;
  total_expense_twd: number;
  advance_deduction_twd: number;
  net_payable_twd: number;
  status: string;
  payment_status: string;
  created_at: string;
}

interface EmployeeItem {
  id: string;
  employee_no: string;
  full_name: string;
}

const activeTab = ref<'requests' | 'settlements'>('requests');
const requests = ref<TravelRequestItem[]>([]);
const settlements = ref<TravelSettlementItem[]>([]);
const employees = ref<EmployeeItem[]>([]);
const isLoading = ref(false);

// 標準出差申請單狀態
const showCreateRequestModal = ref(false);
const formRequestNumber = ref('');
const formApplyDate = ref('');
const formApplicantName = ref('');
const formEmployeeNo = ref('');
const formDepartmentName = ref('');
const formManagerName = ref('');
const formEmployeeId = ref('');

const formPurpose = ref('');
const formRegionType = ref<'DOMESTIC' | 'OVERSEAS'>('DOMESTIC');
const formDestination = ref('');
const formStartDate = ref('');
const formStartTime = ref('09:00');
const formEndDate = ref('');
const formEndTime = ref('18:00');

// 交通方式 (複選)
const formTransportModes = ref<string[]>(['HSR_TRAIN']);
const formTransportOther = ref('');

// 住宿需求
const formNeedsAccommodation = ref(false);
const formAccommodationPlan = ref('');

// 同行與拜訪
const formCompanions = ref('');
const formVisitingTarget = ref('');
const formPlannedAgenda = ref('');
const formExpectedResults = ref('');
const formDeputyEmployeeId = ref('');

// 預估費用明細
const formTransportCost = ref(0);
const formAccommodationCost = ref(0);
const formDailyCost = ref(0);
const formOtherCost = ref(0);

// 備註與預支
const formNotes = ref('');
const formHasAdvance = ref(false);
const formAdvanceCurrency = ref('TWD');
const formAdvanceAmount = ref('0');

const isSaving = ref(false);
const errorMessage = ref('');

// 即時計算出差天數與夜數
const calculatedPeriod = computed(() => {
  if (!formStartDate.value || !formEndDate.value) {
    return { days: 1, nights: 0 };
  }
  const s = new Date(formStartDate.value);
  const e = new Date(formEndDate.value);
  const diffTime = e.getTime() - s.getTime();
  const diffDays = Math.max(0, Math.round(diffTime / (1000 * 60 * 60 * 24)));
  return {
    days: diffDays + 1,
    nights: diffDays,
  };
});

// 即時計算預估費用總額
const calculatedTotalCost = computed(() => {
  return (
    Number(formTransportCost.value || 0) +
    Number(formAccommodationCost.value || 0) +
    Number(formDailyCost.value || 0) +
    Number(formOtherCost.value || 0)
  );
});

// 新增差旅結報狀態
const showCreateSettlementModal = ref(false);
const selectedTravelRequestId = ref('');
const expenseCategory = ref('MEAL');
const expenseDate = ref('');
const expenseCurrency = ref('TWD');
const expenseExchangeRate = ref('1.0000');
const expenseAmount = ref('1200');
const expenseInvoice = ref('INV-9901');
const expenseDesc = ref('出差工作餐');

async function fetchData() {
  isLoading.value = true;
  try {
    const [reqsRes, settsRes, empsRes] = await Promise.all([
      apiFetch(`/api/v1/travel/requests?company_id=${props.companyId}`),
      apiFetch(`/api/v1/travel/settlements?company_id=${props.companyId}`).catch(() => null),
      apiFetch(`/api/v1/hr/employees?company_id=${props.companyId}`).catch(() => null),
    ]);

    if (reqsRes.ok) requests.value = await reqsRes.json();
    if (settsRes && settsRes.ok) settlements.value = await settsRes.json();
    if (empsRes && empsRes.ok) {
      employees.value = await empsRes.json();
      if (!formEmployeeId.value && employees.value.length > 0) {
        formEmployeeId.value = currentUser.value?.employee_id || employees.value[0].id;
      }
    }
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

function openCreateRequest() {
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  const randomSuffix = Math.random().toString(36).substring(2, 6).toUpperCase();

  formRequestNumber.value = `TR-${yyyy}${mm}${dd}-${randomSuffix}`;
  formApplyDate.value = `${yyyy}/${mm}/${dd}`;

  // 申請人身分、工號、部門與主管（依登入者帳號優先自動帶出）
  formEmployeeId.value = currentUser.value?.employee_id || employees.value[0]?.id || '';
  formApplicantName.value = currentUser.value?.display_name || currentUser.value?.username || '吳金樹';
  formEmployeeNo.value = currentUser.value?.employee_no || '0207';
  formDepartmentName.value = currentUser.value?.department_name || '軟體管理一部';
  formManagerName.value = currentUser.value?.manager_name || '詹敦智';

  formPurpose.value = '赴客戶端進行系統上線前整合測試與需求確認';
  formRegionType.value = 'DOMESTIC';
  formDestination.value = '台北市光復路';
  formStartDate.value = todayStr;
  formStartTime.value = '09:00';
  formEndDate.value = todayStr;
  formEndTime.value = '18:00';

  formTransportModes.value = ['HSR_TRAIN'];
  formTransportOther.value = '';
  formNeedsAccommodation.value = false;
  formAccommodationPlan.value = '';
  formCompanions.value = '';
  formVisitingTarget.value = '';
  formPlannedAgenda.value = '1. 上線前整合測試\n2. 系統操作培訓\n3. 客戶簽收確認';
  formExpectedResults.value = '順利通過驗收簽核，完成系統上線交接';

  // 工作代理人：預設挑選第一位非自己的員工
  const otherEmps = employees.value.filter(e => e.id !== formEmployeeId.value);
  formDeputyEmployeeId.value = otherEmps[0]?.id || '';

  formTransportCost.value = 1200;
  formAccommodationCost.value = 0;
  formDailyCost.value = 500;
  formOtherCost.value = 0;
  formNotes.value = '';

  formHasAdvance.value = false;
  formAdvanceCurrency.value = 'TWD';
  formAdvanceAmount.value = '0';
  errorMessage.value = '';

  showCreateRequestModal.value = true;
}

function toggleTransportMode(mode: string) {
  const idx = formTransportModes.value.indexOf(mode);
  if (idx >= 0) {
    formTransportModes.value.splice(idx, 1);
  } else {
    formTransportModes.value.push(mode);
  }
}

async function saveTravelRequest(andSubmit: boolean = false) {
  if (!formPurpose.value.trim() || !formDestination.value.trim() || !formStartDate.value || !formEndDate.value) {
    errorMessage.value = '請填寫完整出差事由、出差地點與起訖日期';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const targetEmployeeId = formEmployeeId.value || currentUser.value?.employee_id || employees.value[0]?.id || '';
    const mainTransport = formTransportModes.value[0] || 'HSR';

    const res = await apiFetch('/api/v1/travel/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: targetEmployeeId,
        title: formPurpose.value.trim(),
        destination: formDestination.value.trim(),
        start_date: formStartDate.value,
        end_date: formEndDate.value,
        transport_mode: mainTransport,
        purpose: formPurpose.value.trim(),
        has_advance: formHasAdvance.value,
        advance_currency: formAdvanceCurrency.value,
        advance_amount: Number(formAdvanceAmount.value || 0),
        deputy_employee_id: formDeputyEmployeeId.value || null,

        // 擴充標準出差表單欄位
        region_type: formRegionType.value,
        start_time: formStartTime.value,
        end_time: formEndTime.value,
        estimated_days: calculatedPeriod.value.days,
        estimated_nights: calculatedPeriod.value.nights,
        transport_modes: formTransportModes.value,
        transport_other: formTransportOther.value,
        needs_accommodation: formNeedsAccommodation.value,
        accommodation_plan: formAccommodationPlan.value,
        companions: formCompanions.value,
        visiting_target: formVisitingTarget.value,
        planned_agenda: formPlannedAgenda.value,
        expected_results: formExpectedResults.value,
        estimated_transport_cost: formTransportCost.value,
        estimated_accommodation_cost: formAccommodationCost.value,
        estimated_daily_cost: formDailyCost.value,
        estimated_other_cost: formOtherCost.value,
        estimated_total_cost: calculatedTotalCost.value,
        notes: formNotes.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '建立出差單失敗');
    }

    const created = await res.json();
    if (andSubmit && created.request_id) {
      const submitRes = await apiFetch(`/api/v1/travel/requests/${created.request_id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!submitRes.ok) {
        const err = await submitRes.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '出差單建立成功，但送審失敗');
      }
    }

    showCreateRequestModal.value = false;
    await fetchData();
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSaving.value = false;
  }
}

async function submitSingleRequest(id: string) {
  try {
    const res = await apiFetch(`/api/v1/travel/requests/${id}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      await fetchData();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.error?.message || err.message || '送審失敗');
    }
  } catch {
    alert('送審連線錯誤');
  }
}

function openCreateSettlement() {
  const approvedReq = requests.value.find(r => r.status === 'APPROVED');
  selectedTravelRequestId.value = approvedReq ? approvedReq.id : (requests.value[0]?.id || '');
  expenseDate.value = new Date().toISOString().split('T')[0];
  showCreateSettlementModal.value = true;
}

async function saveSettlement() {
  if (!selectedTravelRequestId.value) {
    alert('請選擇關聯之出差單');
    return;
  }
  isSaving.value = true;
  try {
    const targetEmployeeId = formEmployeeId.value || currentUser.value?.employee_id || employees.value[0]?.id || '';
    const res = await apiFetch('/api/v1/travel/settlements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: targetEmployeeId,
        travel_request_id: selectedTravelRequestId.value,
        currency: 'TWD',
        items: [
          {
            expense_category: expenseCategory.value,
            expense_date: expenseDate.value,
            currency: expenseCurrency.value,
            exchange_rate: Number(expenseExchangeRate.value),
            amount: Number(expenseAmount.value),
            invoice_number: expenseInvoice.value,
            description: expenseDesc.value,
          },
        ],
        notes: '出差實報實銷結報',
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '差旅結報失敗');
    }

    showCreateSettlementModal.value = false;
    activeTab.value = 'settlements';
    await fetchData();
  } catch (err: any) {
    alert(err.message || '連線錯誤');
  } finally {
    isSaving.value = false;
  }
}

watch(() => props.companyId, () => fetchData());
onMounted(() => fetchData());
</script>

<template>
  <div class="space-y-6">
    <!-- 功能標題列 -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold text-slate-800">✈️ {{ t('travelView.title') }}</h2>
        <p class="text-xs text-text-muted">{{ t('travelView.subtitle') }}</p>
      </div>
      <div class="flex items-center space-x-2">
        <button
          @click="openCreateRequest"
          class="px-3.5 py-1.5 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
        >
          {{ t('travelView.createRequest') }}
        </button>
        <button
          @click="openCreateSettlement"
          class="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 shadow-xs transition cursor-pointer"
        >
          {{ t('travelView.createSettlement') }}
        </button>
      </div>
    </div>

    <!-- 頁籤導航 -->
    <div class="flex space-x-2 border-b border-border-main">
      <button
        @click="activeTab = 'requests'"
        class="px-4 py-2 text-xs font-semibold border-b-2 transition cursor-pointer"
        :class="activeTab === 'requests' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
      >
        ✈️ {{ t('travelView.tabs.requests') }} ({{ requests.length }})
      </button>
      <button
        @click="activeTab = 'settlements'"
        class="px-4 py-2 text-xs font-semibold border-b-2 transition cursor-pointer"
        :class="activeTab === 'settlements' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
      >
        🧾 {{ t('travelView.tabs.settlements') }} ({{ settlements.length }})
      </button>
    </div>

    <!-- 出差單清單 -->
    <div v-if="activeTab === 'requests'" class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="requests.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('travelView.noRequests') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.requestNo') }}</th>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.subject') }}</th>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.destination') }}</th>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.period') }}</th>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.transport') }}</th>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.advance') }}</th>
              <th class="px-4 py-3">{{ t('travelView.requestsTable.status') }}</th>
              <th class="px-4 py-3 text-right">{{ t('travelView.requestsTable.actions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="r in requests" :key="r.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ r.request_number }}</td>
              <td class="px-4 py-3 font-semibold text-slate-800">{{ r.title }}</td>
              <td class="px-4 py-3 text-slate-600">{{ r.destination }}</td>
              <td class="px-4 py-3 font-mono text-[11px] text-slate-600">{{ r.start_date }} ~ {{ r.end_date }}</td>
              <td class="px-4 py-3 text-slate-600">{{ r.transport_mode }}</td>
              <td class="px-4 py-3">
                <span v-if="r.has_advance" class="font-mono font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  {{ r.advance_currency }} {{ r.advance_amount }}
                </span>
                <span v-else class="text-slate-400">{{ t('travelView.requestsTable.noAdvance') }}</span>
              </td>
              <td class="px-4 py-3">
                <StatusBadge :status="r.status" />
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  v-if="r.status === 'DRAFT'"
                  @click="submitSingleRequest(r.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded transition cursor-pointer"
                >
                  {{ t('travelView.requestsTable.submit') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 結報單清單 -->
    <div v-else class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="settlements.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('travelView.noSettlements') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.settlementNo') }}</th>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.associatedRequest') }}</th>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.totalActual') }}</th>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.advanceOffset') }}</th>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.netPayable') }}</th>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.status') }}</th>
              <th class="px-4 py-3">{{ t('travelView.settlementsTable.paymentStatus') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="s in settlements" :key="s.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ s.settlement_number }}</td>
              <td class="px-4 py-3 font-mono text-slate-600 text-[11px]">{{ s.travel_request_id.substring(0, 8) }}...</td>
              <td class="px-4 py-3 font-mono font-semibold text-slate-800">NT$ {{ s.total_expense_twd }}</td>
              <td class="px-4 py-3 font-mono text-amber-700">NT$ {{ s.advance_deduction_twd }}</td>
              <td class="px-4 py-3 font-mono font-bold" :class="s.net_payable_twd >= 0 ? 'text-emerald-600' : 'text-rose-600'">
                NT$ {{ s.net_payable_twd }}
              </td>
              <td class="px-4 py-3">
                <StatusBadge :status="s.status" />
              </td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold" :class="s.payment_status === 'PAID' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'">
                  {{ s.payment_status === 'PAID' ? t('travelView.settlementsTable.paid') : t('travelView.settlementsTable.unpaid') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 標準出差申請單 Modal (比照紙本截圖格狀排版) -->
    <div v-if="showCreateRequestModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div class="bg-white rounded-xl shadow-2xl w-full max-w-4xl border border-slate-300 overflow-hidden my-8 animate-fade-in">
        
        <!-- 表頭標題與右上方單號日期 -->
        <div class="px-6 pt-5 pb-3 border-b border-slate-200 bg-slate-50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h3 class="text-base font-bold text-slate-900 tracking-wide">
              {{ t('travelView.form.modalTitle') }}
            </h3>
            <span class="text-[11px] text-slate-500 font-mono">Business Travel Application Form</span>
          </div>
          
          <div class="flex items-center space-x-6 text-xs text-slate-700 bg-white px-3 py-1.5 rounded-lg border border-slate-200 shadow-2xs font-mono">
            <div>
              <span class="font-semibold text-slate-500 mr-1.5">{{ t('travelView.form.requestNumber') }}:</span>
              <span class="font-bold text-sky-700">{{ formRequestNumber }}</span>
            </div>
            <div class="border-l border-slate-200 pl-4">
              <span class="font-semibold text-slate-500 mr-1.5">{{ t('travelView.form.applyDate') }}:</span>
              <span class="font-bold text-slate-800">{{ formApplyDate }}</span>
            </div>
            <button
              @click="showCreateRequestModal = false"
              class="text-slate-400 hover:text-slate-600 text-lg leading-none cursor-pointer ml-2"
            >
              &times;
            </button>
          </div>
        </div>

        <div class="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200 flex items-center space-x-2">
            <span>⚠️</span>
            <span>{{ errorMessage }}</span>
          </div>

          <!-- 核心格狀外框表格 (Table Grid Border Layout) -->
          <div class="border-2 border-slate-700 rounded-sm overflow-hidden bg-white text-xs text-slate-800 shadow-xs">
            <table class="w-full border-collapse">
              <tbody>
                <!-- 列 1: 申請人 與 部門 -->
                <tr class="border-b border-slate-400">
                  <td class="w-[15%] px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.applicant') }}
                  </td>
                  <td class="w-[35%] px-3 py-2 border-r border-slate-400 bg-slate-50/30">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-slate-900">{{ formApplicantName }}</span>
                      <span class="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                        {{ t('travelView.form.autoPopulated') }}
                      </span>
                    </div>
                  </td>
                  <td class="w-[15%] px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.department') }}
                  </td>
                  <td class="w-[35%] px-3 py-2 bg-slate-50/30">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-slate-900">{{ formDepartmentName }}</span>
                      <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                        {{ t('travelView.form.autoPopulated') }}
                      </span>
                    </div>
                  </td>
                </tr>

                <!-- 列 2: 員工編號 與 主管 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.employeeNo') }}
                  </td>
                  <td class="px-3 py-2 border-r border-slate-400 bg-slate-50/30 font-mono">
                    <span class="font-bold text-slate-900">{{ formEmployeeNo }}</span>
                  </td>
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.manager') }}
                  </td>
                  <td class="px-3 py-2 bg-slate-50/30">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-slate-900">{{ formManagerName }}</span>
                      <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                        {{ t('travelView.form.autoManager') }}
                      </span>
                    </div>
                  </td>
                </tr>

                <!-- 列 3: 出差事由 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.subject') }} <span class="text-rose-500">*</span>
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <input
                      v-model="formPurpose"
                      type="text"
                      :placeholder="t('travelView.form.subjectPlaceholder')"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500 font-medium"
                      required
                    />
                  </td>
                </tr>

                <!-- 列 4: 出差地點 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.destination') }} <span class="text-rose-500">*</span>
                  </td>
                  <td colspan="3" class="px-3 py-2 space-y-2">
                    <div class="flex items-center space-x-6">
                      <label class="flex items-center space-x-1.5 cursor-pointer font-medium text-slate-800">
                        <input type="radio" value="DOMESTIC" v-model="formRegionType" class="text-blue-600 focus:ring-blue-500" />
                        <span>{{ t('travelView.form.domestic') }}</span>
                      </label>
                      <label class="flex items-center space-x-1.5 cursor-pointer font-medium text-slate-800">
                        <input type="radio" value="OVERSEAS" v-model="formRegionType" class="text-blue-600 focus:ring-blue-500" />
                        <span>{{ t('travelView.form.overseas') }}</span>
                      </label>
                    </div>
                    <div>
                      <input
                        v-model="formDestination"
                        type="text"
                        :placeholder="t('travelView.form.destinationPlaceholder')"
                        class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                        required
                      />
                    </div>
                  </td>
                </tr>

                <!-- 列 5: 出差期間 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.period') }} <span class="text-rose-500">*</span>
                  </td>
                  <td colspan="3" class="px-3 py-2.5">
                    <div class="flex flex-wrap items-center gap-3">
                      <div class="flex items-center space-x-1.5">
                        <span class="font-semibold text-slate-600">{{ t('travelView.form.from') }}</span>
                        <input
                          v-model="formStartDate"
                          type="date"
                          class="px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500 bg-white"
                          required
                        />
                        <input
                          v-model="formStartTime"
                          type="time"
                          class="px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500 bg-white"
                        />
                      </div>

                      <div class="flex items-center space-x-1.5">
                        <span class="font-semibold text-slate-600">{{ t('travelView.form.to') }}</span>
                        <input
                          v-model="formEndDate"
                          type="date"
                          class="px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500 bg-white"
                          required
                        />
                        <input
                          v-model="formEndTime"
                          type="time"
                          class="px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500 bg-white"
                        />
                      </div>

                      <div class="px-3 py-1 rounded bg-amber-50 text-amber-800 border border-amber-200 font-semibold font-mono text-xs">
                        {{ t('travelView.form.totalPeriod', { days: calculatedPeriod.days, nights: calculatedPeriod.nights }) }}
                      </div>
                    </div>
                  </td>
                </tr>

                <!-- 列 6: 交通方式 (複選) -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.transportMode') }}
                  </td>
                  <td colspan="3" class="px-3 py-2.5">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                      <label class="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="formTransportModes.includes('COMPANY_CAR')"
                          @change="toggleTransportMode('COMPANY_CAR')"
                          class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>{{ t('travelView.form.transportCompanyCar') }}</span>
                      </label>
                      <label class="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="formTransportModes.includes('HSR_TRAIN')"
                          @change="toggleTransportMode('HSR_TRAIN')"
                          class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>{{ t('travelView.form.transportHsrTrain') }}</span>
                      </label>
                      <label class="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="formTransportModes.includes('BUS')"
                          @change="toggleTransportMode('BUS')"
                          class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>{{ t('travelView.form.transportBus') }}</span>
                      </label>
                      <label class="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="formTransportModes.includes('SELF_DRIVE')"
                          @change="toggleTransportMode('SELF_DRIVE')"
                          class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>{{ t('travelView.form.transportSelfDrive') }}</span>
                      </label>
                      <label class="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          :checked="formTransportModes.includes('AIRPLANE')"
                          @change="toggleTransportMode('AIRPLANE')"
                          class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span>{{ t('travelView.form.transportAirplane') }}</span>
                      </label>
                      <div class="col-span-2 sm:col-span-3 flex items-center space-x-2">
                        <label class="flex items-center space-x-2 cursor-pointer shrink-0">
                          <input
                            type="checkbox"
                            :checked="formTransportModes.includes('OTHER')"
                            @change="toggleTransportMode('OTHER')"
                            class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                          />
                          <span>{{ t('travelView.form.transportOther') }}:</span>
                        </label>
                        <input
                          v-model="formTransportOther"
                          type="text"
                          class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                          placeholder="例如捷運、渡輪、計程車"
                        />
                      </div>
                    </div>
                  </td>
                </tr>

                <!-- 列 7: 住宿需求 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.accommodation') }}
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <div class="flex flex-col sm:flex-row sm:items-center gap-3">
                      <div class="flex items-center space-x-4">
                        <label class="flex items-center space-x-1.5 cursor-pointer font-medium">
                          <input type="radio" :value="true" v-model="formNeedsAccommodation" class="text-blue-600 focus:ring-blue-500" />
                          <span>{{ t('travelView.form.needAccommodation') }}</span>
                        </label>
                        <label class="flex items-center space-x-1.5 cursor-pointer font-medium">
                          <input type="radio" :value="false" v-model="formNeedsAccommodation" class="text-blue-600 focus:ring-blue-500" />
                          <span>{{ t('travelView.form.noAccommodation') }}</span>
                        </label>
                      </div>
                      <div class="flex-1 flex items-center space-x-2">
                        <span class="text-slate-600 font-semibold shrink-0">；{{ t('travelView.form.expectedHotel') }}:</span>
                        <input
                          v-model="formAccommodationPlan"
                          type="text"
                          :placeholder="t('travelView.form.expectedHotelPlaceholder')"
                          class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                  </td>
                </tr>

                <!-- 列 8: 同行人員 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.companions') }}
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <input
                      v-model="formCompanions"
                      type="text"
                      :placeholder="t('travelView.form.companionsPlaceholder')"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    />
                  </td>
                </tr>

                <!-- 列 9: 拜訪對象／單位 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.visitingTarget') }}
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <input
                      v-model="formVisitingTarget"
                      type="text"
                      :placeholder="t('travelView.form.visitingTargetPlaceholder')"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    />
                  </td>
                </tr>

                <!-- 列 10: 預定工作內容 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.plannedAgenda') }}
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <textarea
                      v-model="formPlannedAgenda"
                      rows="2"
                      :placeholder="t('travelView.form.plannedAgendaPlaceholder')"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    ></textarea>
                  </td>
                </tr>

                <!-- 列 11: 預期成果 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.expectedResults') }}
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <textarea
                      v-model="formExpectedResults"
                      rows="2"
                      :placeholder="t('travelView.form.expectedResultsPlaceholder')"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    ></textarea>
                  </td>
                </tr>

                <!-- 列 12: 工作代理人 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.deputy') }} <span class="text-rose-500">*</span>
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <select
                      v-model="formDeputyEmployeeId"
                      class="w-full max-w-md px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                      required
                    >
                      <option value="">-- 請選擇職務代理人 --</option>
                      <option
                        v-for="emp in employees.filter(e => e.id !== formEmployeeId)"
                        :key="emp.id"
                        :value="emp.id"
                      >
                        {{ emp.employee_no }} - {{ emp.full_name }}
                      </option>
                    </select>
                  </td>
                </tr>

                <!-- 列 13: 預估費用 -->
                <tr class="border-b border-slate-400">
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.estimatedExpenses') }}
                  </td>
                  <td colspan="3" class="px-3 py-2.5">
                    <div class="flex flex-wrap items-center gap-y-2 gap-x-4">
                      <div class="flex items-center space-x-1.5">
                        <span class="text-slate-600 font-semibold">{{ t('travelView.form.transportCost') }}:</span>
                        <input
                          v-model.number="formTransportCost"
                          type="number"
                          min="0"
                          class="w-20 px-2 py-1 text-xs rounded border border-slate-300 text-right font-mono"
                        />
                      </div>
                      <div class="flex items-center space-x-1.5">
                        <span class="text-slate-600 font-semibold">；{{ t('travelView.form.accommodationCost') }}:</span>
                        <input
                          v-model.number="formAccommodationCost"
                          type="number"
                          min="0"
                          class="w-20 px-2 py-1 text-xs rounded border border-slate-300 text-right font-mono"
                        />
                      </div>
                      <div class="flex items-center space-x-1.5">
                        <span class="text-slate-600 font-semibold">；{{ t('travelView.form.dailyCost') }}:</span>
                        <input
                          v-model.number="formDailyCost"
                          type="number"
                          min="0"
                          class="w-20 px-2 py-1 text-xs rounded border border-slate-300 text-right font-mono"
                        />
                      </div>
                      <div class="flex items-center space-x-1.5">
                        <span class="text-slate-600 font-semibold">；{{ t('travelView.form.otherCost') }}:</span>
                        <input
                          v-model.number="formOtherCost"
                          type="number"
                          min="0"
                          class="w-20 px-2 py-1 text-xs rounded border border-slate-300 text-right font-mono"
                        />
                      </div>
                      <div class="flex items-center space-x-1.5 bg-blue-50 px-2.5 py-1 rounded border border-blue-200">
                        <span class="font-bold text-blue-900">；{{ t('travelView.form.totalCost') }}:</span>
                        <span class="font-bold font-mono text-blue-700 text-sm">NT$ {{ calculatedTotalCost.toLocaleString() }}</span>
                      </div>
                    </div>
                  </td>
                </tr>

                <!-- 列 14: 備註 -->
                <tr>
                  <td class="px-3 py-2.5 font-bold bg-slate-100 border-r border-slate-400 text-slate-900 text-center">
                    {{ t('travelView.form.notes') }}
                  </td>
                  <td colspan="3" class="px-3 py-2">
                    <textarea
                      v-model="formNotes"
                      rows="2"
                      :placeholder="t('travelView.form.notesPlaceholder')"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                    ></textarea>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 差旅預支款項擴充區塊 (保留現有業務功能) -->
          <div class="p-3 rounded-lg border border-slate-200 bg-slate-50/70 space-y-2">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="checkbox" v-model="formHasAdvance" class="rounded text-blue-600 focus:ring-blue-500" />
              <span class="text-xs font-semibold text-slate-800">需要申請差旅預支款項 (Pre-advance Cash/Fund)</span>
            </label>
            <div v-if="formHasAdvance" class="grid grid-cols-2 gap-4 pt-1">
              <div>
                <label class="block text-[11px] font-semibold text-slate-600 mb-1">預支幣別</label>
                <select v-model="formAdvanceCurrency" class="w-full px-3 py-1.5 text-xs rounded border border-slate-300 bg-white">
                  <option value="TWD">新台幣 (TWD)</option>
                  <option value="JPY">日圓 (JPY)</option>
                  <option value="USD">美元 (USD)</option>
                </select>
              </div>
              <div>
                <label class="block text-[11px] font-semibold text-slate-600 mb-1">預支金額</label>
                <input v-model="formAdvanceAmount" type="number" min="0" class="w-full px-3 py-1.5 text-xs rounded border border-slate-300 font-mono" />
              </div>
            </div>
          </div>
        </div>

        <!-- 底部操作按鈕 -->
        <div class="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end space-x-3">
          <button
            type="button"
            @click="showCreateRequestModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 transition cursor-pointer"
          >
            {{ t('travelView.form.cancel') }}
          </button>
          <button
            type="button"
            @click="saveTravelRequest(false)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg border border-sky-600 text-sky-700 hover:bg-sky-50 transition cursor-pointer"
          >
            {{ t('travelView.form.saveDraft') }}
          </button>
          <button
            type="button"
            @click="saveTravelRequest(true)"
            :disabled="isSaving"
            class="px-5 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition cursor-pointer flex items-center space-x-1.5"
          >
            <span>✈️</span>
            <span>{{ isSaving ? '處理中...' : t('travelView.form.submitForm') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 差旅結報 Modal -->
    <div v-if="showCreateSettlementModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">🧾 填寫差旅結報單</h3>
          <button @click="showCreateSettlementModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <FormField label="關聯出差申請單" required>
            <select v-model="selectedTravelRequestId" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white">
              <option v-for="r in requests" :key="r.id" :value="r.id">
                {{ r.request_number }} - {{ r.title }} ({{ r.status }})
              </option>
            </select>
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="費用項目">
              <select v-model="expenseCategory" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="TRANS">交通費 (Transport)</option>
                <option value="HOTEL">住宿費 (Lodging)</option>
                <option value="MEAL">膳食費 (Meals)</option>
                <option value="OTHER">雜支 (Misc)</option>
              </select>
            </FormField>
            <FormField label="消費日期">
              <input v-model="expenseDate" type="date" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="grid grid-cols-3 gap-3">
            <FormField label="幣別">
              <select v-model="expenseCurrency" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="TWD">TWD</option>
                <option value="JPY">JPY</option>
                <option value="USD">USD</option>
              </select>
            </FormField>
            <FormField label="折合匯率">
              <input v-model="expenseExchangeRate" type="number" step="0.0001" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="原始金額">
              <input v-model="expenseAmount" type="number" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="發票 / 憑證號碼">
              <input v-model="expenseInvoice" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="費用說明">
              <input v-model="expenseDesc" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showCreateSettlementModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="saveSettlement"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer"
          >
            {{ isSaving ? '送出中...' : '確認開立結報' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

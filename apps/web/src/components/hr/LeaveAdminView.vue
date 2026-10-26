<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useTranslation } from 'i18next-vue';
import { apiFetch } from '../../utils/auth';
import LeaveLedgerView from './LeaveLedgerView.vue';

interface EmployeeItem {
  id: string;
  employee_no: string;
  full_name: string;
}

interface LeaveTypeItem {
  id: string;
  company_id: string;
  code: string;
  name: string;
  unit: string;
  requires_attachment: boolean;
  is_paid: boolean;
  paid_type?: string;
}

interface EntitlementPreview {
  employee_id: string;
  employee_no: string;
  full_name: string;
  hire_date: string;
  seniority_text: string;
  years: number;
  months: number;
  days: number;
  entitled_days: number;
  entitled_minutes: number;
  current_balance_minutes: number;
  current_balance_days: number;
  already_granted_in_cycle: boolean;
}

const props = defineProps<{
  companyId: string;
  employees: EmployeeItem[];
}>();

const { t } = useTranslation();

// 當前子頁籤：'types' | 'entitlements' | 'ledger'
const currentSubtab = ref<'types' | 'entitlements' | 'ledger'>('types');

// ==========================================
// 1. 假別主檔 (Leave Types)
// ==========================================
const leaveTypes = ref<LeaveTypeItem[]>([]);
const isLoadingTypes = ref(false);

const showTypeModal = ref(false);
const isEditingType = ref(false);
const typeForm = ref({
  id: '',
  code: '',
  name: '',
  unit: 'HALF_HOUR',
  is_paid: true,
  paid_type: 'FULL',
  requires_attachment: false,
});
const isSavingType = ref(false);
const typeError = ref('');

async function fetchLeaveTypes() {
  isLoadingTypes.value = true;
  try {
    const res = await apiFetch('/api/v1/hr/leave-types');
    if (res.ok) {
      leaveTypes.value = await res.json();
    }
  } catch {
    leaveTypes.value = [];
  } finally {
    isLoadingTypes.value = false;
  }
}

function openCreateType() {
  isEditingType.value = false;
  typeError.value = '';
  typeForm.value = {
    id: '',
    code: '',
    name: '',
    unit: 'HALF_HOUR',
    is_paid: true,
    paid_type: 'FULL',
    requires_attachment: false,
  };
  showTypeModal.value = true;
}

function openEditType(item: LeaveTypeItem) {
  isEditingType.value = true;
  typeError.value = '';
  const resolvedPaidType = item.paid_type || (item.is_paid ? 'FULL' : 'UNPAID');
  typeForm.value = {
    id: item.id,
    code: item.code,
    name: item.name,
    unit: item.unit || 'HALF_HOUR',
    is_paid: resolvedPaidType !== 'UNPAID',
    paid_type: resolvedPaidType,
    requires_attachment: item.requires_attachment,
  };
  showTypeModal.value = true;
}

async function deleteType(item: LeaveTypeItem) {
  if (!confirm(`確定要刪除假別【${item.name} (${item.code})】嗎？若已有使用紀錄將無法刪除。`)) return;
  try {
    const res = await apiFetch(`/api/v1/hr/leave-types/${item.id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json();
      alert(err.message || '刪除失敗');
      return;
    }
    await fetchLeaveTypes();
  } catch (e: any) {
    alert(e.message || '刪除發生異常');
  }
}

async function saveLeaveType() {
  if (!typeForm.value.name.trim()) return;
  if (!isEditingType.value && !typeForm.value.code.trim()) return;

  isSavingType.value = true;
  typeError.value = '';

  const isPaid = typeForm.value.paid_type !== 'UNPAID';

  try {
    let res: Response;
    if (isEditingType.value) {
      res = await apiFetch(`/api/v1/hr/leave-types/${typeForm.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: typeForm.value.name.trim(),
          unit: typeForm.value.unit,
          is_paid: isPaid,
          paid_type: typeForm.value.paid_type,
          requires_attachment: typeForm.value.requires_attachment,
        }),
      });
    } else {
      res = await apiFetch('/api/v1/hr/leave-types', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: typeForm.value.code.trim().toUpperCase(),
          name: typeForm.value.name.trim(),
          unit: typeForm.value.unit,
          is_paid: isPaid,
          paid_type: typeForm.value.paid_type,
          requires_attachment: typeForm.value.requires_attachment,
        }),
      });
    }

    if (!res.ok) {
      const err = await res.json();
      typeError.value = err.message || t('hr.leaveAdmin.saveFailed');
      return;
    }

    showTypeModal.value = false;
    await fetchLeaveTypes();
  } catch (e: any) {
    typeError.value = e.message || t('hr.leaveAdmin.saveFailed');
  } finally {
    isSavingType.value = false;
  }
}

// ==========================================
// 2. 法定特休試算與批次發放 (Entitlements)
// ==========================================
const asOfDate = ref(new Date().toISOString().split('T')[0]);
const entitlements = ref<EntitlementPreview[]>([]);
const isLoadingEntitlements = ref(false);
const selectedEmpIds = ref<string[]>([]);
const isBatchGranting = ref(false);
const grantFeedbackMsg = ref('');

async function fetchEntitlements() {
  isLoadingEntitlements.value = true;
  grantFeedbackMsg.value = '';
  selectedEmpIds.value = [];
  try {
    const res = await apiFetch(
      `/api/v1/hr/leave-entitlement/calculate?company_id=${props.companyId}&as_of_date=${asOfDate.value}`
    );
    if (res.ok) {
      entitlements.value = await res.json();
      // 預設自動勾選「待發放」且應給天數 > 0 的員工
      selectedEmpIds.value = entitlements.value
        .filter((e) => !e.already_granted_in_cycle && e.entitled_days > 0)
        .map((e) => e.employee_id);
    }
  } catch {
    entitlements.value = [];
  } finally {
    isLoadingEntitlements.value = false;
  }
}

const isAllSelected = computed(() => {
  const eligible = entitlements.value.filter((e) => e.entitled_days > 0);
  return eligible.length > 0 && selectedEmpIds.value.length === eligible.length;
});

function toggleSelectAll() {
  const eligible = entitlements.value.filter((e) => e.entitled_days > 0);
  if (isAllSelected.value) {
    selectedEmpIds.value = [];
  } else {
    selectedEmpIds.value = eligible.map((e) => e.employee_id);
  }
}

function toggleSelect(empId: string) {
  const idx = selectedEmpIds.value.indexOf(empId);
  if (idx > -1) {
    selectedEmpIds.value.splice(idx, 1);
  } else {
    selectedEmpIds.value.push(empId);
  }
}

async function grantBatchEntitlements(targetEmpIds?: string[]) {
  const ids = targetEmpIds || selectedEmpIds.value;
  if (ids.length === 0) return;

  // 取得特休假別
  const annualLt = leaveTypes.value.find((lt) =>
    ['ANNUAL', 'SPECIAL', 'ANNUAL_LEAVE'].includes(lt.code.toUpperCase())
  ) || leaveTypes.value[0];

  if (!annualLt) {
    grantFeedbackMsg.value = '未找到特別休假假種主檔，請先至「假別主檔設定」建立';
    return;
  }

  isBatchGranting.value = true;
  grantFeedbackMsg.value = '';

  const grantsPayload = entitlements.value
    .filter((e) => ids.includes(e.employee_id) && e.entitled_days > 0)
    .map((e) => {
      const today = new Date();
      const validFrom = today.toISOString().split('T')[0];
      const nextYear = new Date(today);
      nextYear.setFullYear(today.getFullYear() + 1);
      const validTo = nextYear.toISOString().split('T')[0];

      return {
        employee_id: e.employee_id,
        leave_type_id: annualLt.id,
        amount_minutes: e.entitled_minutes,
        valid_from: validFrom,
        valid_to: validTo,
        notes: `法定年資特休自動核算發放 (服務年資: ${e.seniority_text}, 法定天數: ${e.entitled_days} 天)`,
      };
    });

  try {
    const res = await apiFetch('/api/v1/hr/leave-entitlement/grant-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        grants: grantsPayload,
        batch_notes: `基準日 ${asOfDate.value} 全公司在職員工特休批次發放作業`,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      grantFeedbackMsg.value = t('hr.leaveAdmin.grantSuccessMsg', { count: data.granted_count });
      await fetchEntitlements();
    } else {
      const err = await res.json();
      grantFeedbackMsg.value = err.message || t('hr.leaveAdmin.grantFailedMsg');
    }
  } catch (e: any) {
    grantFeedbackMsg.value = e.message || t('hr.leaveAdmin.grantFailedMsg');
  } finally {
    isBatchGranting.value = false;
  }
}

onMounted(async () => {
  await fetchLeaveTypes();
  await fetchEntitlements();
});
</script>

<template>
  <div class="space-y-6">
    <!-- 次頁籤導覽列 (Subtab Pills) -->
    <div class="flex items-center space-x-2 border-b border-border-main pb-3">
      <button
        @click="currentSubtab = 'types'"
        class="px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer flex items-center space-x-1.5"
        :class="
          currentSubtab === 'types'
            ? 'bg-blue-600 text-white shadow-xs'
            : 'bg-white hover:bg-slate-100 text-slate-700 border border-border-main'
        "
      >
        <span>🏷️</span>
        <span>{{ t('hr.leaveAdmin.subtabTypes') }}</span>
      </button>

      <button
        @click="currentSubtab = 'entitlements'"
        class="px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer flex items-center space-x-1.5"
        :class="
          currentSubtab === 'entitlements'
            ? 'bg-blue-600 text-white shadow-xs'
            : 'bg-white hover:bg-slate-100 text-slate-700 border border-border-main'
        "
      >
        <span>📅</span>
        <span>{{ t('hr.leaveAdmin.subtabEntitlements') }}</span>
      </button>

      <button
        @click="currentSubtab = 'ledger'"
        class="px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer flex items-center space-x-1.5"
        :class="
          currentSubtab === 'ledger'
            ? 'bg-blue-600 text-white shadow-xs'
            : 'bg-white hover:bg-slate-100 text-slate-700 border border-border-main'
        "
      >
        <span>📒</span>
        <span>{{ t('hr.leaveAdmin.subtabLedger') }}</span>
      </button>
    </div>

    <!-- 子頁籤 1: 假別主檔設定 (Leave Types) -->
    <div v-if="currentSubtab === 'types'" class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center space-x-2">
            <h3 class="text-sm font-semibold text-slate-800">{{ t('hr.leaveAdmin.typesTitle') }}</h3>
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
              🌐 {{ t('hr.leaveAdmin.globalScopeBadge', '全組織共用（不分公司）') }}
            </span>
          </div>
          <p class="text-xs text-text-muted">{{ t('hr.leaveAdmin.typesSubtitle') }}</p>
        </div>
        <button
          @click="openCreateType"
          class="px-3.5 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer flex items-center space-x-1.5"
        >
          <span>➕</span>
          <span>{{ t('hr.leaveAdmin.createTypeBtn') }}</span>
        </button>
      </div>

      <!-- 假別表格 -->
      <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-700">
            <thead class="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase border-b border-slate-200">
              <tr>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.code') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.name') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.minUnit') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.salaryPayment') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.requiresAttachment') }}</th>
                <th class="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-if="isLoadingTypes">
                <td colspan="6" class="px-4 py-8 text-center text-slate-400">載入假別資料中...</td>
              </tr>
              <tr v-else-if="leaveTypes.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-slate-400">目前尚無假種主檔設定</td>
              </tr>
              <tr v-for="lt in leaveTypes" :key="lt.id" class="hover:bg-slate-50/50">
                <td class="px-4 py-3 font-mono font-bold text-slate-900">{{ lt.code }}</td>
                <td class="px-4 py-3 font-medium text-slate-900">{{ lt.name }}</td>
                <td class="px-4 py-3">
                  <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
                    {{
                      lt.unit === 'HALF_HOUR' ? t('hr.leaveAdmin.unitHalfHour') :
                      lt.unit === 'ONE_HOUR' ? t('hr.leaveAdmin.unitOneHour') :
                      lt.unit === 'ONE_DAY' ? t('hr.leaveAdmin.unitOneDay') :
                      lt.unit === 'DAYS' ? t('hr.leaveAdmin.unitDays') :
                      lt.unit === 'HOURS' ? t('hr.leaveAdmin.unitHours') :
                      lt.unit === 'MINUTES' ? t('hr.leaveAdmin.unitMinutes') : lt.unit
                    }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span
                    v-if="lt.paid_type === 'FULL' || (!lt.paid_type && lt.is_paid)"
                    class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
                  >
                    {{ t('hr.leaveAdmin.paidFull') }}
                  </span>
                  <span
                    v-else-if="lt.paid_type === 'HALF'"
                    class="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-50 text-sky-700 border border-sky-200"
                  >
                    {{ t('hr.leaveAdmin.paidHalf') }}
                  </span>
                  <span
                    v-else
                    class="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200"
                  >
                    {{ t('hr.leaveAdmin.paidNone') }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span
                    class="px-2 py-0.5 rounded text-[10px] font-semibold"
                    :class="lt.requires_attachment ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-slate-50 text-slate-500'"
                  >
                    {{ lt.requires_attachment ? t('hr.leaveAdmin.attachmentRequired') : t('hr.leaveAdmin.attachmentOptional') }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right space-x-1">
                  <button
                    @click="openEditType(lt)"
                    class="px-2.5 py-1 text-[11px] font-medium rounded border border-slate-200 bg-white hover:bg-slate-50 text-blue-600 cursor-pointer inline-flex items-center space-x-1"
                  >
                    <span>✏️</span>
                    <span>{{ t('hr.leaveAdmin.editTypeBtn') }}</span>
                  </button>
                  <button
                    @click="deleteType(lt)"
                    class="px-2.5 py-1 text-[11px] font-medium rounded border border-rose-200 bg-white hover:bg-rose-50 text-rose-600 cursor-pointer inline-flex items-center space-x-1"
                  >
                    <span>🗑️</span>
                    <span>刪除</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>


    <!-- 子頁籤 2: 法定特休試算與批次發放 (Entitlements) -->
    <div v-else-if="currentSubtab === 'entitlements'" class="space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h3 class="text-sm font-semibold text-slate-800">{{ t('hr.leaveAdmin.entitlementsTitle') }}</h3>
          <p class="text-xs text-text-muted">{{ t('hr.leaveAdmin.entitlementsSubtitle') }}</p>
        </div>

        <div class="flex items-center space-x-2">
          <div class="flex items-center space-x-1.5 text-xs">
            <span class="text-slate-600 font-medium">{{ t('hr.leaveAdmin.asOfDate') }}:</span>
            <input
              type="date"
              v-model="asOfDate"
              class="px-2 py-1 text-xs rounded border border-border-main bg-white focus:outline-hidden focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <button
            @click="fetchEntitlements"
            class="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition cursor-pointer flex items-center space-x-1"
          >
            <span>🔄</span>
            <span>{{ t('hr.leaveAdmin.recalculateBtn') }}</span>
          </button>
          <button
            @click="() => grantBatchEntitlements()"
            :disabled="isBatchGranting || selectedEmpIds.length === 0"
            class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-xs font-semibold text-white shadow-xs transition cursor-pointer flex items-center space-x-1"
          >
            <span>⚡</span>
            <span>{{ isBatchGranting ? '發放中...' : t('hr.leaveAdmin.batchGrantBtn', { count: selectedEmpIds.length }) }}</span>
          </button>
        </div>
      </div>

      <!-- 反饋訊息 -->
      <div
        v-if="grantFeedbackMsg"
        class="p-3 text-xs rounded-lg border"
        :class="grantFeedbackMsg.includes('失敗') || grantFeedbackMsg.includes('未找到') ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'"
      >
        {{ grantFeedbackMsg }}
      </div>

      <!-- 特休年資試算清冊表格 -->
      <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-700">
            <thead class="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase border-b border-slate-200">
              <tr>
                <th class="px-4 py-3 w-8 text-center">
                  <input
                    type="checkbox"
                    :checked="isAllSelected"
                    @change="toggleSelectAll"
                    class="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                  />
                </th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.employeeNo') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.employeeName') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.hireDate') }}</th>
                <th class="px-4 py-3">{{ t('hr.leaveAdmin.seniority') }}</th>
                <th class="px-4 py-3 text-right">{{ t('hr.leaveAdmin.entitledDays') }}</th>
                <th class="px-4 py-3 text-right">{{ t('hr.leaveAdmin.entitledHours') }}</th>
                <th class="px-4 py-3 text-right">{{ t('hr.leaveAdmin.currentBalance') }}</th>
                <th class="px-4 py-3 text-center">{{ t('hr.leaveAdmin.statusCol') }}</th>
                <th class="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-if="isLoadingEntitlements">
                <td colspan="10" class="px-4 py-8 text-center text-slate-400">正在試算全體在職員工法定特休階梯...</td>
              </tr>
              <tr v-else-if="entitlements.length === 0">
                <td colspan="10" class="px-4 py-8 text-center text-slate-400">{{ t('hr.leaveAdmin.noEligibleEmployees') }}</td>
              </tr>
              <tr v-for="item in entitlements" :key="item.employee_id" class="hover:bg-slate-50/50">
                <td class="px-4 py-3 text-center">
                  <input
                    type="checkbox"
                    :checked="selectedEmpIds.includes(item.employee_id)"
                    :disabled="item.entitled_days === 0"
                    @change="toggleSelect(item.employee_id)"
                    class="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer disabled:opacity-30"
                  />
                </td>
                <td class="px-4 py-3 font-mono font-bold text-slate-900">{{ item.employee_no }}</td>
                <td class="px-4 py-3 font-medium text-slate-900">{{ item.full_name }}</td>
                <td class="px-4 py-3 font-mono text-slate-600">{{ item.hire_date }}</td>
                <td class="px-4 py-3 font-medium text-indigo-700">{{ item.seniority_text }}</td>
                <td class="px-4 py-3 text-right font-bold text-slate-900">{{ item.entitled_days }} 天</td>
                <td class="px-4 py-3 text-right font-mono text-slate-600">{{ (item.entitled_minutes / 60).toFixed(1) }} 小時</td>
                <td class="px-4 py-3 text-right font-bold text-emerald-700">{{ item.current_balance_days }} 天</td>
                <td class="px-4 py-3 text-center">
                  <span
                    class="px-2 py-0.5 rounded text-[10px] font-semibold"
                    :class="item.already_granted_in_cycle ? 'bg-slate-100 text-slate-600 border border-slate-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'"
                  >
                    {{ item.already_granted_in_cycle ? t('hr.leaveAdmin.statusGranted') : t('hr.leaveAdmin.statusPending') }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right">
                  <button
                    v-if="!item.already_granted_in_cycle && item.entitled_days > 0"
                    @click="grantBatchEntitlements([item.employee_id])"
                    class="px-2.5 py-1 text-[11px] font-semibold rounded border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 cursor-pointer inline-flex items-center space-x-1"
                  >
                    <span>⚡</span>
                    <span>{{ t('hr.leaveAdmin.grantSingleBtn') }}</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 子頁籤 3: 假額帳本流水帳 (Ledger) -->
    <div v-else-if="currentSubtab === 'ledger'">
      <LeaveLedgerView :companyId="props.companyId" :employees="props.employees" />
    </div>

    <!-- 假別新增/編輯 Modal -->
    <div
      v-if="showTypeModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
    >
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-border-main animate-in fade-in zoom-in-95 duration-150">
        <div class="px-6 py-4 border-b border-border-main flex items-center justify-between bg-slate-50">
          <h3 class="text-sm font-bold text-slate-800">
            {{ isEditingType ? t('hr.leaveAdmin.modalEditTitle') : t('hr.leaveAdmin.modalCreateTitle') }}
          </h3>
          <button
            @click="showTypeModal = false"
            class="text-slate-400 hover:text-slate-600 text-lg leading-none cursor-pointer"
          >
            ✕
          </button>
        </div>

        <form @submit.prevent="saveLeaveType" class="p-6 space-y-4">
          <div v-if="typeError" class="p-2.5 text-xs rounded bg-rose-50 border border-rose-200 text-rose-700">
            {{ typeError }}
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">
              {{ t('hr.leaveAdmin.code') }} <span class="text-rose-500">*</span>
            </label>
            <input
              v-model="typeForm.code"
              :disabled="isEditingType"
              type="text"
              placeholder="例如：ANNUAL, SICK, PERSONAL, MATERNITY"
              class="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-hidden focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100 disabled:text-slate-500 font-mono uppercase"
              required
            />
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">
              {{ t('hr.leaveAdmin.name') }} <span class="text-rose-500">*</span>
            </label>
            <input
              v-model="typeForm.name"
              type="text"
              placeholder="例如：特別休假 (Annual Leave)"
              class="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">
              {{ t('hr.leaveAdmin.minUnit') }}
            </label>
            <select
              v-model="typeForm.unit"
              class="w-full px-3 py-2 text-xs rounded-lg border border-border-main focus:outline-hidden focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="HALF_HOUR">{{ t('hr.leaveAdmin.unitHalfHour') }}</option>
              <option value="ONE_HOUR">{{ t('hr.leaveAdmin.unitOneHour') }}</option>
              <option value="ONE_DAY">{{ t('hr.leaveAdmin.unitOneDay') }}</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">
              {{ t('hr.leaveAdmin.salaryPayment') }}
            </label>
            <div class="flex items-center space-x-5 p-2 rounded-lg bg-slate-50 border border-slate-200">
              <label class="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  value="FULL"
                  v-model="typeForm.paid_type"
                  class="text-blue-600 focus:ring-blue-500"
                />
                <span class="font-medium">{{ t('hr.leaveAdmin.paidFull') }}</span>
              </label>
              <label class="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  value="HALF"
                  v-model="typeForm.paid_type"
                  class="text-blue-600 focus:ring-blue-500"
                />
                <span class="font-medium">{{ t('hr.leaveAdmin.paidHalf') }}</span>
              </label>
              <label class="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  value="UNPAID"
                  v-model="typeForm.paid_type"
                  class="text-blue-600 focus:ring-blue-500"
                />
                <span class="font-medium">{{ t('hr.leaveAdmin.paidNone') }}</span>
              </label>
            </div>
          </div>

          <div class="pt-1">
            <label class="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                v-model="typeForm.requires_attachment"
                class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <span>{{ t('hr.leaveAdmin.attachmentRequired') }}</span>
            </label>
          </div>

          <div class="flex justify-end space-x-2 pt-4 border-t border-border-main">
            <button
              type="button"
              @click="showTypeModal = false"
              class="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
            >
              取消
            </button>
            <button
              type="submit"
              :disabled="isSavingType"
              class="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs cursor-pointer disabled:opacity-50"
            >
              {{ isSavingType ? '儲存中...' : '儲存假種設定' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

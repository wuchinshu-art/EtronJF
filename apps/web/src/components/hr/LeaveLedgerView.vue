<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import DateTimeInput from '../common/DateTimeInput.vue';
import { apiFetch } from '../../utils/auth';

interface QuotaItem {
  leave_type_id: string;
  leave_type_code: string;
  leave_type_name: string;
  unit: string;
  is_paid: boolean;
  requires_attachment: boolean;
  available_minutes: number;
  available_days: number;
  as_of_date: string;
}

interface LedgerEntry {
  id: string;
  leave_type_id: string;
  entry_type: string;
  amount_minutes: number;
  balance_after_minutes: number;
  valid_from: string;
  valid_to: string;
  notes: string | null;
  created_at: string;
}

interface EmployeeItem {
  id: string;
  employee_no: string;
  full_name: string;
}

interface LeaveTypeItem {
  id: string;
  code: string;
  name: string;
}

const props = defineProps<{
  companyId: string;
  employees: EmployeeItem[];
}>();

const { t } = useTranslation();

const selectedEmployeeId = ref('');
const asOfDate = ref(new Date().toISOString().split('T')[0]);
const quotas = ref<QuotaItem[]>([]);
const ledgerEntries = ref<LedgerEntry[]>([]);
const leaveTypes = ref<LeaveTypeItem[]>([]);
const isLoading = ref(false);

// 發放假額 Modal
const showGrantModal = ref(false);
const grantLeaveTypeId = ref('');
const grantDays = ref(1);
const grantValidFrom = ref(new Date().toISOString().split('T')[0]);
const grantValidTo = ref(`${new Date().getFullYear()}-12-31`);
const grantNotes = ref('');
const isGranting = ref(false);
const grantError = ref('');

async function fetchLeaveTypes() {
  try {
    const res = await fetch('/api/v1/hr/leave-types');
    if (res.ok) {
      leaveTypes.value = await res.json();
      if (leaveTypes.value.length > 0 && !grantLeaveTypeId.value) {
        grantLeaveTypeId.value = leaveTypes.value[0].id;
      }
    }
  } catch {
    leaveTypes.value = [];
  }
}

async function loadEmployeeData() {
  if (!selectedEmployeeId.value) {
    quotas.value = [];
    ledgerEntries.value = [];
    return;
  }

  isLoading.value = true;
  try {
    // 1. 查詢可用天數彙總 (480 分鐘標準日換算)
    const qRes = await fetch(`/api/v1/hr/leave-ledger/summary?employee_id=${selectedEmployeeId.value}&as_of_date=${asOfDate.value}`);
    if (qRes.ok) {
      quotas.value = await qRes.json();
    }

    // 2. 查詢不可變帳本流水 (Entries)
    const eRes = await fetch(`/api/v1/hr/leave-ledger/entries?employee_id=${selectedEmployeeId.value}`);
    if (eRes.ok) {
      ledgerEntries.value = await eRes.json();
    }
  } catch {
    quotas.value = [];
    ledgerEntries.value = [];
  } finally {
    isLoading.value = false;
  }
}

async function handleGrant() {
  if (!selectedEmployeeId.value || !grantLeaveTypeId.value || grantDays.value <= 0) {
    grantError.value = '請確認員工、假別與發放天數';
    return;
  }

  isGranting.value = true;
  grantError.value = '';

  try {
    // 1 天 = 480 分鐘標準工時
    const minutes = Math.round(grantDays.value * 480);
    const res = await apiFetch('/api/v1/hr/leave-ledger/grant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: selectedEmployeeId.value,
        leave_type_id: grantLeaveTypeId.value,
        amount_minutes: minutes,
        valid_from: grantValidFrom.value,
        valid_to: grantValidTo.value,
        notes: grantNotes.value || `年度假額發放 (${grantDays.value}天)`,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || '假額發放失敗');
    }

    showGrantModal.value = false;
    grantDays.value = 1;
    grantNotes.value = '';
    loadEmployeeData();
  } catch (err: any) {
    grantError.value = err.message || '連線錯誤';
  } finally {
    isGranting.value = false;
  }
}

watch(
  () => props.employees,
  (emps) => {
    if (emps.length > 0 && !selectedEmployeeId.value) {
      selectedEmployeeId.value = emps[0].id;
      loadEmployeeData();
    }
  },
  { immediate: true }
);

watch(() => props.companyId, () => {
  fetchLeaveTypes();
});

onMounted(() => {
  fetchLeaveTypes();
});
</script>

<template>
  <div class="space-y-6">
    <!-- 頂端控制列 (選擇員工與基準日) -->
    <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-64">
          <label class="block text-xs font-semibold text-slate-700 mb-1">{{ t('hr.ledger.selectEmployeeLabel') }}</label>
          <select
            v-model="selectedEmployeeId"
            @change="loadEmployeeData"
            class="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
          >
            <option value="" disabled>{{ t('hr.ledger.selectEmployee') }}</option>
            <option v-for="emp in props.employees" :key="emp.id" :value="emp.id">
              {{ emp.full_name }} ({{ emp.employee_no }})
            </option>
          </select>
        </div>

        <div class="w-44">
          <label class="block text-xs font-semibold text-slate-700 mb-1">{{ t('hr.ledger.asOfDate') }}</label>
          <DateTimeInput v-model="asOfDate" mode="date" @change="loadEmployeeData" />
        </div>
      </div>

      <button
        @click="showGrantModal = true"
        :disabled="!selectedEmployeeId"
        class="px-3.5 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition disabled:opacity-50 cursor-pointer"
      >
        {{ t('hr.ledger.grantBtn') }}
      </button>
    </div>

    <!-- 1. 可用假額天數即時儀表卡片 -->
    <div>
      <h4 class="text-xs font-semibold text-slate-700 mb-2.5 flex items-center">
        <span class="mr-1.5">📊</span> {{ t('hr.ledger.quotaSummary') }}
      </h4>

      <div v-if="quotas.length === 0" class="text-xs text-slate-400 p-6 bg-white rounded-xl border border-slate-200 text-center">
        {{ t('hr.ledger.promptSelectEmployee') }}
      </div>

      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          v-for="q in quotas"
          :key="q.leave_type_id"
          class="bg-white p-4 rounded-xl border border-border-main shadow-xs hover:border-(--color-primary) transition"
        >
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-semibold text-slate-700">{{ q.leave_type_name }}</span>
            <span
              class="text-[10px] px-2 py-0.5 rounded font-medium"
              :class="q.is_paid ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'"
            >
              {{ q.is_paid ? t('hr.ledger.paidLeave') : t('hr.ledger.unpaidLeave') }}
            </span>
          </div>
          <div class="flex items-baseline space-x-2">
            <span class="text-2xl font-extrabold text-(--color-primary) font-mono">{{ q.available_days }}</span>
            <span class="text-xs font-medium text-slate-500">{{ t('hr.ledger.daysUnit') }}</span>
          </div>
          <div class="text-[11px] text-text-muted mt-1 font-mono">
            {{ t('hr.ledger.availableMinutesUnit', { minutes: q.available_minutes }) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 不可變流水帳本 DataTable -->
    <div class="bg-white rounded-xl border border-border-main shadow-xs p-4">
      <div class="flex items-center justify-between mb-3">
        <h4 class="text-xs font-semibold text-slate-700 flex items-center">
          <span class="mr-1.5">📜</span> {{ t('hr.ledger.auditStream') }}
        </h4>
        <span class="text-[11px] text-text-muted">{{ t('hr.ledger.reverseOrder') }}</span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-700">
          <thead class="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase border-b border-slate-200">
            <tr>
              <th class="px-3 py-2.5">{{ t('hr.ledger.txTimeUtc') }}</th>
              <th class="px-3 py-2.5">{{ t('hr.ledger.leaveTypeCode') }}</th>
              <th class="px-3 py-2.5">{{ t('hr.ledger.entryType') }}</th>
              <th class="px-3 py-2.5 text-right">{{ t('hr.ledger.amountMinutes') }}</th>
              <th class="px-3 py-2.5 text-right">{{ t('hr.ledger.balanceAfter') }}</th>
              <th class="px-3 py-2.5">{{ t('hr.ledger.validPeriod') }}</th>
              <th class="px-3 py-2.5">{{ t('hr.ledger.notes') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="ledgerEntries.length === 0">
              <td colspan="7" class="px-3 py-8 text-center text-slate-400">
                {{ t('table.empty') }}
              </td>
            </tr>
            <tr v-for="entry in ledgerEntries" :key="entry.id" class="hover:bg-slate-50/50">
              <td class="px-3 py-2.5 font-mono text-[11px] text-slate-500">
                {{ new Date(entry.created_at).toISOString().replace('T', ' ').slice(0, 19) }}
              </td>
              <td class="px-3 py-2.5 font-medium">{{ entry.leave_type_id }}</td>
              <td class="px-3 py-2.5">
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-bold font-mono"
                  :class="{
                    'bg-emerald-100 text-emerald-800': entry.entry_type === 'GRANT',
                    'bg-amber-100 text-amber-800': entry.entry_type === 'HOLD',
                    'bg-rose-100 text-rose-800': entry.entry_type === 'COMMIT',
                    'bg-sky-100 text-sky-800': entry.entry_type === 'RELEASE',
                  }"
                >
                  {{ entry.entry_type }}
                </span>
              </td>
              <td
                class="px-3 py-2.5 text-right font-mono font-bold"
                :class="entry.amount_minutes >= 0 ? 'text-emerald-600' : 'text-rose-600'"
              >
                {{ entry.amount_minutes >= 0 ? `+${entry.amount_minutes}` : entry.amount_minutes }} 分
              </td>
              <td class="px-3 py-2.5 text-right font-mono text-slate-800">
                {{ entry.balance_after_minutes }} 分 ({{ (entry.balance_after_minutes / 480).toFixed(2) }}天)
              </td>
              <td class="px-3 py-2.5 font-mono text-[11px] text-slate-600">
                {{ entry.valid_from }} ~ {{ entry.valid_to }}
              </td>
              <td class="px-3 py-2.5 text-slate-600">{{ entry.notes || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 發放假額 Modal -->
    <div v-if="showGrantModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">{{ t('hr.ledger.grantModalTitle') }}</h3>
          <button @click="showGrantModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="grantError" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ grantError }}
          </div>

          <FormField :label="t('hr.ledger.leaveType')" required>
            <select
              v-model="grantLeaveTypeId"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            >
              <option v-for="lt in leaveTypes" :key="lt.id" :value="lt.id">
                {{ lt.name }} ({{ lt.code }})
              </option>
            </select>
          </FormField>

          <FormField :label="t('hr.ledger.grantDays')" required>
            <input
              v-model.number="grantDays"
              type="number"
              step="0.5"
              min="0.5"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            />
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.ledger.validFrom')" required>
              <DateTimeInput v-model="grantValidFrom" mode="date" />
            </FormField>
            <FormField :label="t('hr.ledger.validTo')" required>
              <DateTimeInput v-model="grantValidTo" mode="date" />
            </FormField>
          </div>

          <FormField :label="t('hr.ledger.notes')">
            <input
              v-model="grantNotes"
              type="text"
              :placeholder="t('hr.ledger.grantNotesPlaceholder')"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            />
          </FormField>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showGrantModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-white transition cursor-pointer"
          >
            {{ t('actions.cancel') }}
          </button>
          <button
            @click="handleGrant"
            :disabled="isGranting"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs disabled:opacity-50 transition cursor-pointer"
          >
            {{ isGranting ? t('status.loading') : t('hr.ledger.confirmGrant') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

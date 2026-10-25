<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import DateTimeInput from '../common/DateTimeInput.vue';
import { apiFetch } from '../../utils/auth';

export interface ShiftSummaryOption {
  id: string;
  name: string;
  code: string;
  work_start_time: string;
  work_end_time: string;
  timezone?: string;
}

const props = defineProps<{
  isOpen: boolean;
  mode: 'transfer' | 'resign';
  employee: {
    id: string;
    employee_no: string;
    company_id?: string;
    full_name: string;
    organization_id: string;
    job_title?: string | null;
    job_grade?: string | null;
    default_shift_id?: string | null;
  } | null;
  organizations?: Array<{ id: string; name: string; code: string }>;
  shifts?: ShiftSummaryOption[];
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'success'): void;
}>();

const { t } = useTranslation();

const newOrganizationId = ref('');
const newJobTitle = ref('');
const newJobGrade = ref('');
const newDefaultShiftId = ref('');
const effectiveDate = ref(new Date().toISOString().split('T')[0]);
const notes = ref('');
const isSubmitting = ref(false);
const errorMessage = ref('');

const isResign = computed(() => props.mode === 'resign');

// 自主取得之部門與班別清單 (具備父層 Fallback 與自我修復能力)
const localOrganizations = ref<Array<{ id: string; name: string; code: string }>>([]);
const localShifts = ref<ShiftSummaryOption[]>([]);

const effectiveOrganizations = computed(() => {
  if (localOrganizations.value.length > 0) return localOrganizations.value;
  return props.organizations || [];
});

const effectiveShifts = computed(() => {
  if (localShifts.value.length > 0) return localShifts.value;
  return props.shifts || [];
});

async function loadOrgsAndShifts(companyId?: string) {
  if (!companyId) return;
  try {
    const [orgRes, shiftRes] = await Promise.all([
      apiFetch(`/api/v1/hr/organizations?company_id=${companyId}`),
      apiFetch(`/api/v1/hr/shifts?company_id=${companyId}`),
    ]);
    if (orgRes.ok) localOrganizations.value = await orgRes.json();
    if (shiftRes.ok) localShifts.value = await shiftRes.json();
  } catch (err) {
    console.error('Failed to load orgs/shifts in transfer modal', err);
  }
}

watch(
  () => [props.isOpen, props.employee?.company_id],
  ([open, compId]) => {
    if (open && compId) {
      loadOrgsAndShifts(compId as string);
    }
  }
);

watch(
  () => props.employee,
  (emp) => {
    if (emp) {
      newOrganizationId.value = emp.organization_id || '';
      newJobTitle.value = emp.job_title || '';
      newJobGrade.value = emp.job_grade || '';
      newDefaultShiftId.value = emp.default_shift_id || '';
      effectiveDate.value = new Date().toISOString().split('T')[0];
      notes.value = '';
      errorMessage.value = '';
    }
  },
  { immediate: true }
);

function getShiftDesc(shiftId?: string | null) {
  if (!shiftId) return '-';
  const found = effectiveShifts.value.find((s) => s.id === shiftId);
  return found ? `${found.name} (${found.code})` : shiftId;
}

async function handleSubmit() {
  if (!props.employee) return;
  if (!isResign.value && !newOrganizationId.value && !newJobTitle.value.trim() && newDefaultShiftId.value === (props.employee.default_shift_id || '')) {
    errorMessage.value = '請至少選擇新調動部門、輸入新職位職稱或調整班別';
    return;
  }

  isSubmitting.value = true;
  errorMessage.value = '';

  try {
    const endpoint = isResign.value
      ? `/api/v1/hr/employees/${props.employee.id}/resign`
      : `/api/v1/hr/employees/${props.employee.id}/transfer`;

    const payload = isResign.value
      ? { resign_date: effectiveDate.value, notes: notes.value }
      : {
          new_organization_id: newOrganizationId.value || undefined,
          new_job_title: newJobTitle.value.trim() || undefined,
          new_job_grade: newJobGrade.value.trim() || undefined,
          new_default_shift_id: newDefaultShiftId.value !== (props.employee.default_shift_id || '') ? (newDefaultShiftId.value || null) : undefined,
          effective_date: effectiveDate.value,
          notes: notes.value,
        };

    const res = await apiFetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || '作業執行失敗');
    }

    emit('success');
    emit('close');
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div v-if="props.isOpen && props.employee" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden animate-fade-in">
      <div
        class="px-6 py-4 border-b flex items-center justify-between"
        :class="isResign ? 'bg-rose-50/70 border-rose-100 text-rose-800' : 'bg-slate-50 border-slate-100 text-slate-800'"
      >
        <h3 class="text-base font-semibold flex items-center">
          <span class="mr-2">{{ isResign ? '⚠️' : '🔄' }}</span>
          {{ isResign ? t('hr.transferModal.resignTitle') : t('hr.transferModal.transferTitle') }}
        </h3>
        <button @click="emit('close')" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
      </div>

      <div class="p-6 space-y-4">
        <!-- 員工資訊卡 -->
        <div class="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex justify-between items-center">
          <div>
            <span class="text-slate-500">{{ t('hr.transferModal.employeeLabel') }}:</span>
            <span class="font-bold text-slate-800 ml-1.5">{{ props.employee.full_name }} ({{ props.employee.employee_no }})</span>
            <div v-if="props.employee.job_title" class="text-[11px] text-slate-400 mt-0.5">
              {{ t('hr.transferModal.currentTitle') }}：{{ props.employee.job_title }}
            </div>
            <div v-if="props.employee.default_shift_id" class="text-[11px] text-slate-500 mt-0.5 flex items-center">
              <span>⏱️ {{ t('hr.transferModal.currentShift') }}：</span>
              <span class="font-semibold text-slate-700 ml-1">
                {{ getShiftDesc(props.employee.default_shift_id) }}
              </span>
            </div>
          </div>
          <span class="text-[11px] px-2 py-0.5 rounded bg-slate-200 text-slate-700 font-mono">
            {{ props.employee.id.slice(0, 8) }}
          </span>
        </div>

        <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
          ⚠️ {{ errorMessage }}
        </div>

        <div v-if="isResign" class="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-800 text-xs">
          🚨 <strong>{{ t('hr.transferModal.securityAlert') }}：</strong>{{ t('hr.transferModal.resignWarning') }}
        </div>

        <!-- 異動欄位 (調動部門、變更職位/職等) -->
        <div v-if="!isResign" class="space-y-3">
          <FormField :label="t('hr.transferModal.newDept')" required>
            <select
              v-model="newOrganizationId"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
            >
              <option value="" disabled>{{ t('hr.transferModal.selectNewDept') }}</option>
              <option v-for="org in effectiveOrganizations" :key="org.id" :value="org.id">
                {{ org.name }} ({{ org.code }})
              </option>
            </select>
          </FormField>

          <div class="grid grid-cols-2 gap-3">
            <FormField :label="t('hr.transferModal.newJobTitle')">
              <input
                v-model="newJobTitle"
                type="text"
                :placeholder="t('hr.transferModal.newJobTitlePlaceholder')"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>

            <FormField :label="t('hr.transferModal.newJobGrade')">
              <input
                v-model="newJobGrade"
                type="text"
                :placeholder="t('hr.transferModal.newJobGradePlaceholder')"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <!-- 調動班別選擇 -->
          <FormField :label="t('hr.transferModal.newShift')">
            <select
              v-model="newDefaultShiftId"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
            >
              <option value="">{{ t('hr.transferModal.keepCurrentShift') }}</option>
              <option v-for="s in effectiveShifts" :key="s.id" :value="s.id">
                {{ s.name }} ({{ s.code }} &bull; {{ s.work_start_time }} ~ {{ s.work_end_time }})
              </option>
            </select>
          </FormField>
        </div>

        <FormField :label="isResign ? t('hr.transferModal.resignEffectiveDate') : t('hr.transferModal.effectiveDate')" required>
          <DateTimeInput v-model="effectiveDate" mode="date" />
        </FormField>

        <FormField :label="t('hr.transferModal.notes')">
          <textarea
            v-model="notes"
            rows="2"
            :placeholder="t('hr.transferModal.notesPlaceholder')"
            class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
          ></textarea>
        </FormField>
      </div>

      <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
        <button
          @click="emit('close')"
          type="button"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 hover:bg-white text-slate-700 transition cursor-pointer"
        >
          {{ t('actions.cancel') }}
        </button>
        <button
          @click="handleSubmit"
          :disabled="isSubmitting"
          type="button"
          class="px-4 py-2 text-xs font-semibold rounded-lg text-white shadow-xs disabled:opacity-50 transition cursor-pointer"
          :class="isResign ? 'bg-rose-600 hover:bg-rose-700' : 'bg-(--color-primary) hover:bg-primary-hover'"
        >
          {{ isSubmitting ? t('status.loading') : (isResign ? t('hr.transferModal.confirmResign') : t('hr.transferModal.confirmTransfer')) }}
        </button>
      </div>
    </div>
  </div>
</template>

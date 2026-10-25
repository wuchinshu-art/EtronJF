<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import DateTimeInput from '../common/DateTimeInput.vue';
import { apiFetch } from '../../utils/auth';

interface PersonOption {
  id: string;
  national_id: string | null;
  full_name: string;
  english_name: string | null;
  mobile_phone: string | null;
  personal_email: string | null;
  current_companies: string[];
}

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
  companyId: string;
  organizations?: Array<{ id: string; name: string; code: string }>;
  shifts?: ShiftSummaryOption[];
  targetPerson?: any | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'success'): void;
  (e: 'open-create-person'): void;
}>();

const { t } = useTranslation();

const personList = ref<PersonOption[]>([]);
const isLoadingPersons = ref(false);
const selectedPersonId = ref<string>('');
const selectedPersonData = ref<PersonOption | null>(null);

// 自主取得之部門與班別清單 (具備父層 Fallback 與自我修復能力)
const localOrganizations = ref<Array<{ id: string; name: string; code: string }>>([]);
const isLoadingOrgs = ref(false);
const localShifts = ref<ShiftSummaryOption[]>([]);
const isLoadingShifts = ref(false);

const effectiveOrganizations = computed(() => {
  if (localOrganizations.value.length > 0) return localOrganizations.value;
  return props.organizations || [];
});

const effectiveShifts = computed(() => {
  if (localShifts.value.length > 0) return localShifts.value;
  return props.shifts || [];
});

// 報到時對應之任職資訊欄位
const employeeNo = ref('');
const email = ref('');
const organizationId = ref('');
const defaultShiftId = ref('');
const jobTitle = ref('');
const jobGrade = ref('');
const employmentType = ref('REGULAR');
const hireDate = ref(new Date().toISOString().split('T')[0]);
const probationEndDate = ref('');

const createUserAccount = ref(true);
const initialPassword = ref('Welcome123!');
const isSubmitting = ref(false);
const errorMessage = ref('');

// 讀取可供報到之人員清單
async function loadPersons() {
  isLoadingPersons.value = true;
  try {
    const res = await apiFetch('/api/v1/hr/persons');
    if (res.ok) {
      personList.value = await res.json();
      applyTargetPerson();
    }
  } catch (err) {
    console.error('Failed to load persons', err);
  } finally {
    isLoadingPersons.value = false;
  }
}

function applyTargetPerson() {
  if (props.targetPerson) {
    selectedPersonId.value = props.targetPerson.id;
    selectedPersonData.value = props.targetPerson;
  } else if (selectedPersonId.value) {
    const found = personList.value.find((p) => p.id === selectedPersonId.value);
    selectedPersonData.value = found || null;
  } else {
    selectedPersonData.value = null;
  }
}

watch(selectedPersonId, (newId) => {
  const found = personList.value.find((p) => p.id === newId);
  selectedPersonData.value = found || null;
});

watch(
  () => props.targetPerson,
  (tp) => {
    if (tp) {
      selectedPersonId.value = tp.id;
      selectedPersonData.value = tp;
    }
  }
);

async function loadOrganizations(companyId: string) {
  if (!companyId) return;
  isLoadingOrgs.value = true;
  try {
    const res = await apiFetch(`/api/v1/hr/organizations?company_id=${companyId}`);
    if (res.ok) {
      const data = await res.json();
      localOrganizations.value = Array.isArray(data) ? data : [];
      if (!organizationId.value && localOrganizations.value.length > 0) {
        organizationId.value = localOrganizations.value[0].id;
      }
    }
  } catch (err) {
    console.error('Failed to load organizations in modal', err);
  } finally {
    isLoadingOrgs.value = false;
  }
}

async function loadShifts(companyId: string) {
  if (!companyId) return;
  isLoadingShifts.value = true;
  try {
    const res = await apiFetch(`/api/v1/hr/shifts?company_id=${companyId}`);
    if (res.ok) {
      const data = await res.json();
      localShifts.value = Array.isArray(data) ? data : [];
      if (!defaultShiftId.value && localShifts.value.length > 0) {
        defaultShiftId.value = localShifts.value[0].id;
      }
    }
  } catch (err) {
    console.error('Failed to load shifts in modal', err);
  } finally {
    isLoadingShifts.value = false;
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      errorMessage.value = '';
      employeeNo.value = '';
      email.value = '';
      organizationId.value = '';
      defaultShiftId.value = '';
      jobTitle.value = '';
      jobGrade.value = '';
      employmentType.value = 'REGULAR';
      hireDate.value = new Date().toISOString().split('T')[0];
      probationEndDate.value = '';
      createUserAccount.value = true;
      initialPassword.value = 'Welcome123!';
      loadPersons();
      loadOrganizations(props.companyId);
      loadShifts(props.companyId);
    }
  }
);

watch(
  () => props.companyId,
  (newComp) => {
    if (props.isOpen && newComp) {
      loadOrganizations(newComp);
      loadShifts(newComp);
    }
  }
);

async function submitOnboard() {
  if (!selectedPersonId.value) {
    errorMessage.value = '請選擇要辦理報到的員工對象';
    return;
  }
  if (!employeeNo.value.trim() || !email.value.trim() || !organizationId.value || !hireDate.value) {
    errorMessage.value = '請填寫完整報到資訊 (本公司工號、公務信箱、所屬部門、到職日期)';
    return;
  }

  isSubmitting.value = true;
  errorMessage.value = '';

  try {
    const payload = {
      person_id: selectedPersonId.value,
      full_name: selectedPersonData.value?.full_name || '',
      employee_no: employeeNo.value.trim(),
      company_id: props.companyId,
      organization_id: organizationId.value,
      default_shift_id: defaultShiftId.value || null,
      email: email.value.trim(),
      hire_date: hireDate.value,
      job_title: jobTitle.value.trim() || null,
      job_grade: jobGrade.value.trim() || null,
      employment_type: employmentType.value,
      probation_end_date: probationEndDate.value || null,
      create_user_account: createUserAccount.value,
      initial_password: createUserAccount.value ? initialPassword.value : undefined,
    };

    const res = await apiFetch('/api/v1/hr/employees', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || '報到作業失敗');
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
  <div v-if="props.isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-xl border border-slate-200 overflow-hidden animate-fade-in flex flex-col max-h-[92vh]">
      <!-- 頂部標題與說明 -->
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
        <div>
          <h3 class="text-base font-semibold text-slate-800 flex items-center">
            <span class="mr-2">📝</span> {{ t('hr.onboardModal.title') }}
          </h3>
          <p class="text-[11px] text-slate-500 mt-0.5">
            {{ t('hr.onboardModal.subtitle', { companyId: props.companyId }) }}
          </p>
        </div>
        <button @click="emit('close')" class="text-slate-400 hover:text-slate-600 text-xl leading-none cursor-pointer">&times;</button>
      </div>

      <!-- 報到表單本體 -->
      <div class="p-6 overflow-y-auto space-y-4 flex-1">
        <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
          ⚠️ {{ errorMessage }}
        </div>

        <!-- 區塊 1: 報到對象 (Person) -->
        <div class="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
          <div class="flex items-center justify-between">
            <label class="text-xs font-semibold text-slate-800 flex items-center">
              <span class="mr-1.5">🪪</span> {{ t('hr.onboardModal.targetPerson') }} <span class="text-rose-500 ml-1">*</span>
            </label>
            <button
              type="button"
              @click="emit('open-create-person')"
              class="text-xs text-(--color-primary) hover:underline font-medium cursor-pointer"
            >
              {{ t('hr.onboardModal.createPersonFirst') }}
            </button>
          </div>

          <!-- 若為指定人員鎖定顯示，否則顯示下拉挑選 -->
          <div v-if="props.targetPerson" class="p-2.5 bg-white rounded-lg border border-slate-200 flex items-center justify-between text-xs">
            <div>
              <span class="font-bold text-slate-900 text-sm">{{ props.targetPerson.full_name }}</span>
              <span v-if="props.targetPerson.english_name" class="ml-1 text-slate-400">({{ props.targetPerson.english_name }})</span>
              <div class="text-[11px] text-slate-500 mt-0.5 font-mono">
                身分代號: {{ props.targetPerson.national_id || '-' }} ｜ 手機: {{ props.targetPerson.mobile_phone || '-' }}
              </div>
            </div>
            <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              {{ t('hr.onboardModal.lockedTarget') }}
            </span>
          </div>

          <div v-else class="space-y-2">
            <select
              v-model="selectedPersonId"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
            >
              <option value="" disabled>{{ t('hr.onboardModal.selectPersonPrompt') }}</option>
              <option
                v-for="p in personList"
                :key="p.id"
                :value="p.id"
              >
                {{ p.full_name }} ({{ p.national_id || '無身分號' }}) {{ p.current_companies.length > 0 ? `[兼任: ${p.current_companies.join(',')}]` : '' }}
              </option>
            </select>

            <!-- 選中人員摘要卡片 -->
            <div v-if="selectedPersonData" class="p-2.5 bg-white rounded-lg border border-slate-200 text-xs space-y-1">
              <div class="font-bold text-slate-800">
                已選定：{{ selectedPersonData.full_name }}
                <span v-if="selectedPersonData.english_name" class="font-normal text-slate-400">({{ selectedPersonData.english_name }})</span>
              </div>
              <div class="text-[11px] text-slate-500 flex flex-wrap gap-x-3">
                <span>身分識別：{{ selectedPersonData.national_id || '-' }}</span>
                <span>私人信箱：{{ selectedPersonData.personal_email || '-' }}</span>
                <span>私人手機：{{ selectedPersonData.mobile_phone || '-' }}</span>
              </div>
              <div v-if="selectedPersonData.current_companies.length > 0" class="text-[11px] text-indigo-700 font-medium">
                🌐 目前於集團其他公司在職中：{{ selectedPersonData.current_companies.join(', ') }} (報到將自動關聯)
              </div>
            </div>
          </div>
        </div>

        <!-- 區塊 2: 本公司任職資訊 (填寫報到時對應的資訊) -->
        <div class="space-y-4 pt-1">
          <h4 class="text-xs font-semibold text-slate-800 flex items-center">
            <span class="mr-1.5">🏢</span> {{ t('hr.onboardModal.employmentSection') }}
          </h4>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="`${t('hr.employee.no')} (${t('hr.onboardModal.companyEmployeeNo')})`" required>
              <input
                v-model="employeeNo"
                type="text"
                placeholder="例如 TW207 / JP105"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono font-bold"
              />
            </FormField>

            <FormField :label="`${t('hr.employee.email')} (${t('hr.onboardModal.companyEmail')})`" required>
              <input
                v-model="email"
                type="email"
                placeholder="例如 user@etron.com"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.employee.dept')" required>
              <div class="space-y-1">
                <select
                  v-model="organizationId"
                  :disabled="isLoadingOrgs"
                  class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer disabled:bg-slate-100"
                >
                  <option value="" disabled>
                    {{ isLoadingOrgs ? t('hr.onboardModal.loadingDepts') : (effectiveOrganizations.length === 0 ? t('hr.onboardModal.noDeptsInCompany', { companyId: props.companyId }) : t('hr.onboardModal.selectDept')) }}
                  </option>
                  <option v-for="org in effectiveOrganizations" :key="org.id" :value="org.id">
                    {{ org.name }} ({{ org.code }})
                  </option>
                </select>
                <p v-if="!isLoadingOrgs && effectiveOrganizations.length === 0" class="text-[11px] text-amber-600">
                  {{ t('hr.onboardModal.noDeptsHint') }}
                </p>
              </div>
            </FormField>

            <FormField :label="t('hr.employee.hireDate')" required>
              <DateTimeInput v-model="hireDate" mode="date" />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.employee.employmentType')">
              <select
                v-model="employmentType"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
              >
                <option value="REGULAR">{{ t('hr.employmentTypes.regular') }}</option>
                <option value="PROBATION">{{ t('hr.employmentTypes.probation') }}</option>
                <option value="CONTRACT">{{ t('hr.employmentTypes.contract') }}</option>
                <option value="INTERN">{{ t('hr.employmentTypes.intern') }}</option>
                <option value="PART_TIME">{{ t('hr.employmentTypes.partTime') }}</option>
              </select>
            </FormField>

            <FormField :label="t('hr.onboardModal.defaultShift')">
              <select
                v-model="defaultShiftId"
                :disabled="isLoadingShifts"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
              >
                <option value="">{{ t('hr.onboardModal.noDefaultShift') }}</option>
                <option v-for="s in effectiveShifts" :key="s.id" :value="s.id">
                  {{ s.name }} ({{ s.code }} &bull; {{ s.work_start_time }} ~ {{ s.work_end_time }})
                </option>
              </select>
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.employee.jobTitle')">
              <input
                v-model="jobTitle"
                type="text"
                placeholder="例如 首席工程師 / 部門經理"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>

            <FormField :label="t('hr.employee.jobGrade')">
              <input
                v-model="jobGrade"
                type="text"
                placeholder="例如 P4, M1"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <FormField :label="t('hr.employee.probationEndDate')">
            <DateTimeInput v-model="probationEndDate" mode="date" />
          </FormField>

          <!-- 登入帳號同步開通選項 -->
          <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
            <label class="flex items-center space-x-2.5 cursor-pointer">
              <input
                v-model="createUserAccount"
                type="checkbox"
                class="w-4 h-4 rounded text-(--color-primary) focus:ring-0"
              />
              <span class="text-xs font-semibold text-slate-800">{{ t('hr.onboardModal.createAccount') }}</span>
            </label>

            <div v-if="createUserAccount" class="space-y-1.5 pl-6">
              <FormField :label="t('hr.onboardModal.initialPassword')">
                <input
                  v-model="initialPassword"
                  type="text"
                  class="w-full px-3 py-1.5 text-xs font-mono rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>
              <p class="text-[11px] text-text-muted">
                🔒 {{ t('hr.onboardModal.accountHint') }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部按鈕群 -->
      <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/80 flex justify-between items-center">
        <div class="text-[11px] text-slate-400">
          {{ t('hr.onboardModal.finishHint') }}
        </div>

        <div class="flex space-x-2">
          <button
            @click="emit('close')"
            type="button"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 hover:bg-white text-slate-700 transition cursor-pointer"
          >
            {{ t('actions.cancel') }}
          </button>
          <button
            @click="submitOnboard"
            :disabled="isSubmitting"
            type="button"
            class="px-5 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs disabled:opacity-50 transition cursor-pointer"
          >
            {{ isSubmitting ? t('status.loading') : t('hr.onboardModal.completeOnboard') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

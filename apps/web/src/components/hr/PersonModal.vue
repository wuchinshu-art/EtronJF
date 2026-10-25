<script setup lang="ts">
import { ref, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import DateTimeInput from '../common/DateTimeInput.vue';
import { apiFetch } from '../../utils/auth';

interface EducationItem {
  school_name: string;
  major: string;
  start_year: string;
  end_year: string;
  status: string;
}

interface WorkExpItem {
  company_name: string;
  job_title: string;
  job_description: string;
  years_of_service: string;
}

const props = defineProps<{
  isOpen: boolean;
  personId?: string | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved', person: any): void;
}>();

const { t } = useTranslation();

const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref('');

// 人員個資完整表單 (符合標準新進員工基本資料表)
const form = ref({
  full_name: '',
  english_name: '',
  national_id: '',
  birth_date: '',
  gender: 'NOT_SPECIFIED',
  nationality: 'TW',
  marital_status: 'SINGLE',
  blood_type: 'A',
  military_service_status: '免役',
  driving_licenses: '',
  transportation_modes: '',
  height_cm: null as number | null,
  weight_kg: null as number | null,
  contact_phone: '',
  personal_email: '',
  mobile_phone: '',
  residential_address: '',
  permanent_address: '',
  emergency_contact_name: '',
  emergency_contact_relationship: '',
  emergency_contact_phone: '',
  emergency_contact_mobile: '',
  education_history: [] as EducationItem[],
  work_experience: [] as WorkExpItem[],
});

function copyResidentialAddress() {
  form.value.permanent_address = form.value.residential_address;
}

function addEducationRow() {
  form.value.education_history.push({
    school_name: '',
    major: '',
    start_year: '',
    end_year: '',
    status: '畢業',
  });
}

function removeEducationRow(index: number) {
  form.value.education_history.splice(index, 1);
}

function addWorkExpRow() {
  form.value.work_experience.push({
    company_name: '',
    job_title: '',
    job_description: '',
    years_of_service: '',
  });
}

function removeWorkExpRow(index: number) {
  form.value.work_experience.splice(index, 1);
}

function resetForm() {
  form.value = {
    full_name: '',
    english_name: '',
    national_id: '',
    birth_date: '',
    gender: 'NOT_SPECIFIED',
    nationality: 'TW',
    marital_status: 'SINGLE',
    blood_type: 'A',
    military_service_status: '免役',
    driving_licenses: '',
    transportation_modes: '',
    height_cm: null,
    weight_kg: null,
    contact_phone: '',
    personal_email: '',
    mobile_phone: '',
    residential_address: '',
    permanent_address: '',
    emergency_contact_name: '',
    emergency_contact_relationship: '',
    emergency_contact_phone: '',
    emergency_contact_mobile: '',
    education_history: [],
    work_experience: [],
  };
}

async function loadPersonDetail() {
  if (!props.personId) {
    resetForm();
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';
  try {
    const res = await apiFetch(`/api/v1/hr/persons/${props.personId}`);
    if (res.ok) {
      const data = await res.json();
      form.value = {
        full_name: data.full_name || '',
        english_name: data.english_name || '',
        national_id: data.national_id || '',
        birth_date: data.birth_date || '',
        gender: data.gender || 'NOT_SPECIFIED',
        nationality: data.nationality || 'TW',
        marital_status: data.marital_status || 'SINGLE',
        blood_type: data.blood_type || 'A',
        military_service_status: data.military_service_status || '免役',
        driving_licenses: data.driving_licenses || '',
        transportation_modes: data.transportation_modes || '',
        height_cm: data.height_cm ?? null,
        weight_kg: data.weight_kg ?? null,
        contact_phone: data.contact_phone || '',
        personal_email: data.personal_email || '',
        mobile_phone: data.mobile_phone || '',
        residential_address: data.residential_address || '',
        permanent_address: data.permanent_address || '',
        emergency_contact_name: data.emergency_contact_name || '',
        emergency_contact_relationship: data.emergency_contact_relationship || '',
        emergency_contact_phone: data.emergency_contact_phone || '',
        emergency_contact_mobile: data.emergency_contact_mobile || '',
        education_history: Array.isArray(data.education_history) ? data.education_history : [],
        work_experience: Array.isArray(data.work_experience) ? data.work_experience : [],
      };
    } else {
      errorMessage.value = t('hr.persons.modal.loadFailed');
    }
  } catch (err: any) {
    errorMessage.value = err.message || t('hr.persons.modal.connectionError');
  } finally {
    isLoading.value = false;
  }
}

async function handleSave() {
  if (!form.value.full_name.trim()) {
    errorMessage.value = t('hr.persons.modal.requiredName');
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  const payload = {
    full_name: form.value.full_name.trim(),
    english_name: form.value.english_name?.trim() || null,
    national_id: form.value.national_id?.trim() || null,
    birth_date: form.value.birth_date || null,
    gender: form.value.gender,
    nationality: form.value.nationality?.trim() || 'TW',
    marital_status: form.value.marital_status,
    blood_type: form.value.blood_type?.trim() || null,
    military_service_status: form.value.military_service_status?.trim() || null,
    driving_licenses: form.value.driving_licenses?.trim() || null,
    transportation_modes: form.value.transportation_modes?.trim() || null,
    height_cm: form.value.height_cm ? Number(form.value.height_cm) : null,
    weight_kg: form.value.weight_kg ? Number(form.value.weight_kg) : null,
    contact_phone: form.value.contact_phone?.trim() || null,
    personal_email: form.value.personal_email?.trim() || null,
    mobile_phone: form.value.mobile_phone?.trim() || null,
    residential_address: form.value.residential_address?.trim() || null,
    permanent_address: form.value.permanent_address?.trim() || null,
    emergency_contact_name: form.value.emergency_contact_name?.trim() || null,
    emergency_contact_relationship: form.value.emergency_contact_relationship?.trim() || null,
    emergency_contact_phone: form.value.emergency_contact_phone?.trim() || null,
    emergency_contact_mobile: form.value.emergency_contact_mobile?.trim() || null,
    education_history: form.value.education_history.filter(e => e.school_name.trim()),
    work_experience: form.value.work_experience.filter(w => w.company_name.trim()),
  };

  try {
    let res: Response;
    if (props.personId) {
      res = await apiFetch(`/api/v1/hr/persons/${props.personId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      res = await apiFetch('/api/v1/hr/persons', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    if (res.ok) {
      const savedData = await res.json();
      emit('saved', savedData);
      emit('close');
    } else {
      const err = await res.json();
      errorMessage.value = err.message || err.detail || '儲存人員基本資料失敗';
    }
  } catch (err: any) {
    errorMessage.value = err.message || '連線異常';
  } finally {
    isSaving.value = false;
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      errorMessage.value = '';
      loadPersonDetail();
    }
  }
);
</script>

<template>
  <div v-if="props.isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-4xl border border-slate-200 overflow-hidden animate-fade-in flex flex-col max-h-[94vh]">
      <!-- 頂部標題與關閉 -->
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
        <div>
          <h3 class="text-base font-semibold text-slate-800 flex items-center">
            <span class="mr-2">🪪</span> {{ props.personId ? t('hr.persons.modal.editTitle') : t('hr.persons.modal.createTitle') }}
          </h3>
          <p class="text-[11px] text-slate-500 mt-0.5">
            {{ t('hr.persons.modal.desc') }}
          </p>
        </div>
        <button @click="emit('close')" class="text-slate-400 hover:text-slate-600 text-xl leading-none cursor-pointer">&times;</button>
      </div>

      <!-- 表單內容 (可捲動) -->
      <div class="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
        <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
          ⚠️ {{ errorMessage }}
        </div>

        <div v-if="isLoading" class="py-12 text-center text-xs text-slate-400">
          ⏳ {{ t('hr.persons.modal.loading') }}
        </div>

        <div v-else class="space-y-6">
          <!-- 區塊 1: 基本資料與生理資訊 (Personal Profile) -->
          <div class="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 space-y-3">
            <div class="font-bold text-slate-800 text-xs flex items-center border-b border-slate-200/60 pb-2">
              <span class="mr-1.5">👤</span> {{ t('hr.persons.modal.basicSection') }}
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <FormField :label="t('hr.employee.name')" required>
                <input
                  v-model="form.full_name"
                  type="text"
                  :placeholder="t('hr.persons.modal.fullNamePlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.employee.nationalId')">
                <input
                  v-model="form.national_id"
                  type="text"
                  :placeholder="t('hr.persons.modal.nationalIdPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
                />
              </FormField>

              <FormField :label="t('hr.employee.birthDate')">
                <DateTimeInput v-model="form.birth_date" mode="date" />
              </FormField>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <FormField :label="t('hr.employee.gender')">
                <select
                  v-model="form.gender"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
                >
                  <option value="NOT_SPECIFIED">{{ t('hr.genders.notSpecified') }}</option>
                  <option value="FEMALE">{{ t('hr.genders.female') }}</option>
                  <option value="MALE">{{ t('hr.genders.male') }}</option>
                  <option value="OTHER">{{ t('hr.genders.other') }}</option>
                </select>
              </FormField>

              <FormField :label="t('hr.persons.modal.bloodType')">
                <select
                  v-model="form.blood_type"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
                >
                  <option value="A">{{ t('hr.persons.modal.bloodTypeA') }}</option>
                  <option value="B">{{ t('hr.persons.modal.bloodTypeB') }}</option>
                  <option value="O">{{ t('hr.persons.modal.bloodTypeO') }}</option>
                  <option value="AB">{{ t('hr.persons.modal.bloodTypeAB') }}</option>
                  <option value="OTHER">{{ t('hr.persons.modal.bloodTypeOther') }}</option>
                </select>
              </FormField>

              <FormField :label="t('hr.employee.maritalStatus')">
                <select
                  v-model="form.marital_status"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
                >
                  <option value="SINGLE">{{ t('hr.maritalStatuses.single') }}</option>
                  <option value="MARRIED">{{ t('hr.maritalStatuses.married') }}</option>
                  <option value="DIVORCED">{{ t('hr.maritalStatuses.divorced') }}</option>
                  <option value="WIDOWED">{{ t('hr.maritalStatuses.widowed') }}</option>
                </select>
              </FormField>

              <FormField :label="t('hr.persons.modal.militaryStatus')">
                <select
                  v-model="form.military_service_status"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
                >
                  <option value="免役">{{ t('hr.persons.modal.militaryExempt') }}</option>
                  <option value="役畢">{{ t('hr.persons.modal.militaryCompleted') }}</option>
                  <option value="未役">{{ t('hr.persons.modal.militaryPending') }}</option>
                  <option value="服役中">{{ t('hr.persons.modal.militaryServing') }}</option>
                </select>
              </FormField>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <FormField :label="t('hr.persons.modal.drivingLicenses')">
                <input
                  v-model="form.driving_licenses"
                  type="text"
                  :placeholder="t('hr.persons.modal.drivingLicensesPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.persons.modal.transportationModes')">
                <input
                  v-model="form.transportation_modes"
                  type="text"
                  :placeholder="t('hr.persons.modal.transportationModesPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.persons.modal.height')">
                <input
                  v-model.number="form.height_cm"
                  type="number"
                  :placeholder="t('hr.persons.modal.heightPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.persons.modal.weight')">
                <input
                  v-model.number="form.weight_kg"
                  type="number"
                  :placeholder="t('hr.persons.modal.weightPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>
            </div>
          </div>

          <!-- 區塊 2: 通訊聯絡與地址 (Contact & Addresses) -->
          <div class="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 space-y-3">
            <div class="font-bold text-slate-800 text-xs flex items-center border-b border-slate-200/60 pb-2">
              <span class="mr-1.5">📞</span> {{ t('hr.persons.modal.contactSection') }}
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <FormField :label="t('hr.persons.modal.contactPhone')">
                <input
                  v-model="form.contact_phone"
                  type="text"
                  :placeholder="t('hr.persons.modal.contactPhonePlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.employee.mobilePhone')">
                <input
                  v-model="form.mobile_phone"
                  type="text"
                  :placeholder="t('hr.persons.modal.mobilePhonePlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.employee.personalEmail')">
                <input
                  v-model="form.personal_email"
                  type="email"
                  :placeholder="t('hr.persons.modal.personalEmailPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>
            </div>

            <FormField :label="t('hr.employee.residentialAddress')">
              <input
                v-model="form.residential_address"
                type="text"
                :placeholder="t('hr.persons.modal.residentialAddressPlaceholder')"
                class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>

            <FormField :label="t('hr.employee.permanentAddress')">
              <div class="flex items-center space-x-2">
                <input
                  v-model="form.permanent_address"
                  type="text"
                  :placeholder="t('hr.persons.modal.permanentAddressPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
                <button
                  type="button"
                  @click="copyResidentialAddress"
                  class="px-2.5 py-1.5 text-[11px] font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 whitespace-nowrap cursor-pointer shadow-2xs"
                >
                  {{ t('hr.persons.modal.sameAsContact') }}
                </button>
              </div>
            </FormField>
          </div>

          <!-- 區塊 3: 緊急聯絡人 (Emergency Contact) -->
          <div class="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 space-y-3">
            <div class="font-bold text-slate-800 text-xs flex items-center border-b border-slate-200/60 pb-2">
              <span class="mr-1.5">🚨</span> {{ t('hr.persons.modal.emergencySection') }}
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <FormField :label="t('hr.employee.emergencyContact', '緊急聯絡人姓名')">
                <input
                  v-model="form.emergency_contact_name"
                  type="text"
                  :placeholder="t('hr.persons.modal.emergencyContactNamePlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.employee.emergencyRelationship', '與聯絡人關係')">
                <input
                  v-model="form.emergency_contact_relationship"
                  type="text"
                  :placeholder="t('hr.persons.modal.emergencyRelationshipPlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.employee.emergencyPhone', '聯絡電話 (市話)')">
                <input
                  v-model="form.emergency_contact_phone"
                  type="text"
                  :placeholder="t('hr.persons.modal.emergencyPhonePlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>

              <FormField :label="t('hr.persons.modal.emergencyMobile', '緊急聯絡人行動電話')">
                <input
                  v-model="form.emergency_contact_mobile"
                  type="text"
                  :placeholder="t('hr.persons.modal.emergencyMobilePlaceholder')"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                />
              </FormField>
            </div>
          </div>

          <!-- 區塊 4: 學歷 (Education Background) -->
          <div class="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 space-y-3">
            <div class="flex items-center justify-between border-b border-slate-200/60 pb-2">
              <div class="font-bold text-slate-800 text-xs flex items-center">
                <span class="mr-1.5">🎓</span> {{ t('hr.persons.modal.eduSection') }}
              </div>
              <button
                type="button"
                @click="addEducationRow"
                class="px-2.5 py-1 text-[11px] font-semibold text-blue-600 bg-white border border-blue-200 rounded-lg hover:bg-blue-50 cursor-pointer shadow-2xs"
              >
                {{ t('hr.persons.modal.addEduBtn') }}
              </button>
            </div>

            <div v-if="form.education_history.length === 0" class="py-4 text-center text-slate-400 text-[11px]">
              {{ t('hr.persons.modal.noEdu') }}
            </div>

            <div v-else class="space-y-2">
              <div
                v-for="(edu, idx) in form.education_history"
                :key="idx"
                class="p-2.5 bg-white rounded-lg border border-slate-200/80 grid grid-cols-1 sm:grid-cols-12 gap-2 items-center"
              >
                <div class="sm:col-span-4">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.schoolName') }}</label>
                  <input
                    v-model="edu.school_name"
                    type="text"
                    :placeholder="t('hr.persons.modal.schoolNamePlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-3">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.major') }}</label>
                  <input
                    v-model="edu.major"
                    type="text"
                    :placeholder="t('hr.persons.modal.majorPlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-2">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.startYear') }}</label>
                  <input
                    v-model="edu.start_year"
                    type="text"
                    :placeholder="t('hr.persons.modal.startYearPlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-2">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.endYear') }}</label>
                  <input
                    v-model="edu.end_year"
                    type="text"
                    :placeholder="t('hr.persons.modal.endYearPlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-1 flex items-end justify-center pt-3 sm:pt-0">
                  <button
                    type="button"
                    @click="removeEducationRow(idx)"
                    class="text-rose-500 hover:text-rose-700 p-1 text-sm cursor-pointer"
                    :title="t('hr.persons.modal.deleteRowTooltip')"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 區塊 5: 工作經歷 (Work Experience) -->
          <div class="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 space-y-3">
            <div class="flex items-center justify-between border-b border-slate-200/60 pb-2">
              <div class="font-bold text-slate-800 text-xs flex items-center">
                <span class="mr-1.5">💼</span> {{ t('hr.persons.modal.expSection') }}
              </div>
              <button
                type="button"
                @click="addWorkExpRow"
                class="px-2.5 py-1 text-[11px] font-semibold text-blue-600 bg-white border border-blue-200 rounded-lg hover:bg-blue-50 cursor-pointer shadow-2xs"
              >
                {{ t('hr.persons.modal.addExpBtn') }}
              </button>
            </div>

            <div v-if="form.work_experience.length === 0" class="py-4 text-center text-slate-400 text-[11px]">
              {{ t('hr.persons.modal.noExp') }}
            </div>

            <div v-else class="space-y-2">
              <div
                v-for="(exp, idx) in form.work_experience"
                :key="idx"
                class="p-2.5 bg-white rounded-lg border border-slate-200/80 grid grid-cols-1 sm:grid-cols-12 gap-2 items-center"
              >
                <div class="sm:col-span-3">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.companyName') }}</label>
                  <input
                    v-model="exp.company_name"
                    type="text"
                    :placeholder="t('hr.persons.modal.companyNamePlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-2">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.jobTitle') }}</label>
                  <input
                    v-model="exp.job_title"
                    type="text"
                    :placeholder="t('hr.persons.modal.jobTitlePlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-5">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.jobDesc') }}</label>
                  <input
                    v-model="exp.job_description"
                    type="text"
                    :placeholder="t('hr.persons.modal.jobDescPlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden"
                  />
                </div>
                <div class="sm:col-span-1">
                  <label class="block text-[10px] text-slate-400 mb-0.5">{{ t('hr.persons.modal.yearsOfService') }}</label>
                  <input
                    v-model="exp.years_of_service"
                    type="text"
                    :placeholder="t('hr.persons.modal.yearsPlaceholder')"
                    class="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:outline-hidden text-center"
                  />
                </div>
                <div class="sm:col-span-1 flex items-end justify-center pt-3 sm:pt-0">
                  <button
                    type="button"
                    @click="removeWorkExpRow(idx)"
                    class="text-rose-500 hover:text-rose-700 p-1 text-sm cursor-pointer"
                    :title="t('hr.persons.modal.deleteRowTooltip')"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作按鈕 -->
      <div class="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-end space-x-3">
        <button
          type="button"
          @click="emit('close')"
          class="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition cursor-pointer"
        >
          {{ t('hr.persons.modal.cancel') }}
        </button>
        <button
          type="button"
          :disabled="isSaving"
          @click="handleSave"
          class="px-5 py-2 text-xs font-bold text-white bg-(--color-primary) hover:bg-primary-hover rounded-xl shadow-xs transition disabled:opacity-50 cursor-pointer flex items-center"
        >
          <span v-if="isSaving" class="animate-spin mr-1.5">⏳</span>
          <span>{{ isSaving ? t('hr.persons.modal.saving') : t('hr.persons.modal.save') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

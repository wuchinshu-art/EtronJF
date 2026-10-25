<script setup lang="ts">
import { ref, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { apiFetch } from '../../utils/auth';

const props = defineProps<{
  isOpen: boolean;
  employeeId: string | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'updated'): void;
}>();

const { t } = useTranslation();

const isLoading = ref(false);
const isEditing = ref(false);
const isSaving = ref(false);
const errorMessage = ref('');
const employeeData = ref<any>(null);

// 可編輯欄位
const editForm = ref({
  english_name: '',
  job_title: '',
  job_grade: '',
  mobile_phone: '',
  personal_email: '',
  residential_address: '',
  permanent_address: '',
  emergency_contact_name: '',
  emergency_contact_relationship: '',
  emergency_contact_phone: '',
});

async function loadDetail() {
  if (!props.employeeId) return;
  isLoading.value = true;
  errorMessage.value = '';
  isEditing.value = false;

  try {
    const res = await fetch(`/api/v1/hr/employees/${props.employeeId}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || '讀取員工資料失敗');
    }
    const data = await res.json();
    employeeData.value = data;

    // 同步到編輯表單
    editForm.value = {
      english_name: data.english_name || '',
      job_title: data.job_title || '',
      job_grade: data.job_grade || '',
      mobile_phone: data.mobile_phone || '',
      personal_email: data.personal_email || '',
      residential_address: data.residential_address || '',
      permanent_address: data.permanent_address || '',
      emergency_contact_name: data.emergency_contact_name || '',
      emergency_contact_relationship: data.emergency_contact_relationship || '',
      emergency_contact_phone: data.emergency_contact_phone || '',
    };
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isLoading.value = false;
  }
}

async function saveEdit() {
  if (!props.employeeId) return;
  isSaving.value = true;
  errorMessage.value = '';

  try {
    const res = await apiFetch(`/api/v1/hr/employees/${props.employeeId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || '更新資料失敗');
    }

    await loadDetail();
    emit('updated');
  } catch (err: any) {
    errorMessage.value = err.message || '更新錯誤';
  } finally {
    isSaving.value = false;
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open && props.employeeId) {
      loadDetail();
    }
  }
);
</script>

<template>
  <div v-if="props.isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl border border-slate-200 overflow-hidden animate-fade-in flex flex-col max-h-[90vh]">
      <!-- 頂部 -->
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-base shadow-xs">
            {{ employeeData?.full_name ? employeeData.full_name[0] : '員' }}
          </div>
          <div>
            <h3 class="text-base font-semibold text-slate-800 flex items-center space-x-2">
              <span>{{ employeeData?.full_name }}</span>
              <span v-if="employeeData?.english_name" class="text-xs font-normal text-slate-500">({{ employeeData.english_name }})</span>
              <span
                :class="[
                  'px-2 py-0.5 text-[10px] font-semibold rounded-full',
                  employeeData?.status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'
                ]"
              >
                {{ employeeData?.status === 'ACTIVE' ? t('hr.employee.active') : t('hr.employee.resigned') }}
              </span>
            </h3>
            <p class="text-[11px] text-slate-500 font-mono mt-0.5">
              {{ employeeData?.employee_no }} &bull; {{ employeeData?.job_title || t('hr.employeeDetailModal.unspecifiedTitle') }}
            </p>
          </div>
        </div>
        <button @click="emit('close')" class="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
      </div>

      <!-- 內容主體 -->
      <div class="p-6 overflow-y-auto space-y-5 flex-1">
        <div v-if="isLoading" class="py-12 text-center text-xs text-slate-500">
          <span class="animate-spin inline-block mr-2">⏳</span> {{ t('status.loading') }}
        </div>

        <div v-else-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
          ⚠️ {{ errorMessage }}
        </div>

        <div v-else-if="employeeData" class="space-y-5">
          <!-- 1. 基本身分與主管卡片 -->
          <div class="bg-slate-50/80 border border-slate-200 rounded-xl p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-bold text-slate-700 flex items-center">
                <span class="mr-1.5">🪪</span> {{ t('hr.employeeDetailModal.identityAndManager') }}
              </h4>
              <span class="text-[10px] text-slate-400 font-mono">{{ t('hr.employeeDetailModal.version', { version: employeeData.version }) }}</span>
            </div>
            <div class="grid grid-cols-3 gap-3 text-xs">
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.employeeDetailModal.nationalIdProtected') }}</span>
                <span class="font-mono font-semibold text-slate-800">{{ employeeData.national_id || t('hr.employeeDetailModal.notSpecified') }}</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.employeeDetailModal.genderBirth') }}</span>
                <span class="text-slate-800">{{ employeeData.gender }} &bull; {{ employeeData.birth_date || t('hr.employeeDetailModal.notSpecified') }}</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.employeeDetailModal.nationalityMarital') }}</span>
                <span class="text-slate-800">{{ employeeData.nationality || '-' }} &bull; {{ employeeData.marital_status }}</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.persons.modal.bloodType') }} / {{ t('hr.persons.modal.militaryService') }}</span>
                <span class="text-slate-800">{{ employeeData.blood_type || '-' }} &bull; {{ employeeData.military_service_status || '-' }}</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.persons.modal.height') }} / {{ t('hr.persons.modal.weight') }}</span>
                <span class="text-slate-800">{{ employeeData.height_cm ? employeeData.height_cm + ' cm' : '-' }} &bull; {{ employeeData.weight_kg ? employeeData.weight_kg + ' kg' : '-' }}</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.persons.modal.drivingLicense') }} / {{ t('hr.persons.modal.transportation') }}</span>
                <span class="text-slate-800">{{ employeeData.driving_licenses || '-' }} &bull; {{ employeeData.transportation_modes || '-' }}</span>
              </div>
            </div>

            <!-- 直屬主管與預設班別 -->
            <div class="pt-2 border-t border-slate-200/60 flex items-center justify-between text-xs">
              <div class="flex items-center space-x-3">
                <div class="flex items-center space-x-1.5">
                  <span class="text-slate-500">{{ t('hr.employeeDetailModal.directManager') }}：</span>
                  <span v-if="employeeData.manager" class="font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    {{ employeeData.manager.manager_name }} ({{ employeeData.manager.manager_no }})
                  </span>
                  <span v-else class="text-slate-400 italic">{{ t('hr.employeeDetailModal.noManager') }}</span>
                </div>
                <div v-if="employeeData.default_shift_id" class="flex items-center space-x-1 text-slate-600">
                  <span>⏱️ {{ t('hr.employee.defaultShift') }}：</span>
                  <span class="font-semibold text-slate-800 font-mono">{{ employeeData.default_shift_id }}</span>
                </div>
              </div>
              <div class="text-[11px] text-slate-400">
                {{ t('hr.employeeDetailModal.hireDate') }}：{{ employeeData.hire_date }}
              </div>
            </div>
          </div>

          <!-- 集團跨公司任職記錄 -->
          <div v-if="employeeData.other_employments && employeeData.other_employments.length > 0" class="p-3 bg-indigo-50/80 border border-indigo-200 rounded-xl space-y-2 text-xs">
            <div class="font-semibold text-indigo-900 flex items-center justify-between">
              <span class="flex items-center">
                <span class="mr-1.5">🌐</span> {{ t('hr.employeeDetailModal.groupConcurrent') }}
              </span>
              <span class="text-[10px] text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full font-semibold">
                {{ t('hr.employeeDetailModal.concurrentCount', { count: employeeData.other_employments.length }) }}
              </span>
            </div>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="oe in employeeData.other_employments"
                :key="oe.id"
                class="inline-flex items-center px-2.5 py-1 rounded-lg bg-white border border-indigo-200 text-indigo-800 text-[11px] font-mono shadow-xs"
              >
                🏢 {{ oe.company_id }} &bull; {{ oe.employee_no }} ({{ oe.job_title || '-' }}) &bull; {{ oe.status === 'ACTIVE' ? t('hr.employeeDetailModal.active') : t('hr.employeeDetailModal.resigned') }}
              </span>
            </div>
          </div>

          <!-- 2. 聯絡資訊與緊急聯絡人 (可切換編輯模式) -->
          <div class="border border-slate-200 rounded-xl p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-bold text-slate-700 flex items-center">
                <span class="mr-1.5">📞</span> {{ t('hr.employeeDetailModal.contactAndEmergency') }}
              </h4>
              <button
                v-if="!isEditing"
                type="button"
                @click="isEditing = true"
                class="px-2.5 py-1 text-[11px] font-semibold rounded-md border border-slate-300 hover:bg-slate-50 text-slate-700 transition"
              >
                ✏️ {{ t('hr.employee.editBtn') }}
              </button>
            </div>

            <!-- 檢視模式 -->
            <div v-if="!isEditing" class="space-y-3 text-xs">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <span class="text-slate-400 block text-[11px]">{{ t('hr.employee.email') }}</span>
                  <span class="text-slate-800">{{ employeeData.email }}</span>
                </div>
                <div>
                  <span class="text-slate-400 block text-[11px]">{{ t('hr.employee.personalEmail') }}</span>
                  <span class="text-slate-800">{{ employeeData.personal_email || '-' }}</span>
                </div>
              </div>
              <div class="grid grid-cols-3 gap-3">
                <div>
                  <span class="text-slate-400 block text-[11px]">{{ t('hr.persons.modal.contactPhone') }}</span>
                  <span class="text-slate-800">{{ employeeData.contact_phone || '-' }}</span>
                </div>
                <div>
                  <span class="text-slate-400 block text-[11px]">{{ t('hr.employee.mobilePhone') }}</span>
                  <span class="text-slate-800">{{ employeeData.mobile_phone || '-' }}</span>
                </div>
                <div>
                  <span class="text-slate-400 block text-[11px]">{{ t('hr.employee.jobTitle') }} / {{ t('hr.employee.jobGrade') }}</span>
                  <span class="text-slate-800">{{ employeeData.job_title || '-' }} ({{ employeeData.job_grade || '-' }})</span>
                </div>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.employee.residentialAddress') }}</span>
                <span class="text-slate-800">{{ employeeData.residential_address || '-' }}</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">{{ t('hr.employee.permanentAddress') }}</span>
                <span class="text-slate-800">{{ employeeData.permanent_address || '-' }}</span>
              </div>

              <!-- 緊急聯絡人 -->
              <div class="bg-rose-50/40 p-3 rounded-lg border border-rose-100 flex items-center justify-between">
                <div>
                  <span class="text-[11px] text-rose-700 font-semibold block">🆘 {{ t('hr.employee.emergencyContact') }}</span>
                  <span class="text-slate-800 font-medium">
                    {{ employeeData.emergency_contact_name || t('hr.employeeDetailModal.notSpecified') }}
                    <span v-if="employeeData.emergency_contact_relationship" class="text-slate-500 font-normal">({{ employeeData.emergency_contact_relationship }})</span>
                  </span>
                </div>
                <div class="text-right space-y-0.5">
                  <span class="text-[11px] text-slate-400 block">{{ t('hr.employee.emergencyPhone') }} / {{ t('hr.persons.modal.emergencyMobile') }}</span>
                  <span class="font-mono text-slate-800 font-semibold">
                    {{ employeeData.emergency_contact_phone || '-' }} &bull; {{ employeeData.emergency_contact_mobile || '-' }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 編輯模式 -->
            <div v-else class="space-y-3">
              <div class="grid grid-cols-2 gap-3">
                <FormField :label="t('hr.employee.jobTitle')">
                  <input v-model="editForm.job_title" type="text" class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300" />
                </FormField>
                <FormField :label="t('hr.employee.jobGrade')">
                  <input v-model="editForm.job_grade" type="text" class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300" />
                </FormField>
              </div>

              <div class="grid grid-cols-2 gap-3">
                <FormField :label="t('hr.employee.mobilePhone')">
                  <input v-model="editForm.mobile_phone" type="tel" class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300" />
                </FormField>
                <FormField :label="t('hr.employee.personalEmail')">
                  <input v-model="editForm.personal_email" type="email" class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300" />
                </FormField>
              </div>

              <FormField :label="t('hr.employee.residentialAddress')">
                <input v-model="editForm.residential_address" type="text" class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300" />
              </FormField>

              <FormField :label="t('hr.employee.permanentAddress')">
                <input v-model="editForm.permanent_address" type="text" class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300" />
              </FormField>

              <div class="p-3 bg-slate-50 rounded-lg space-y-2 border border-slate-200">
                <span class="text-xs font-semibold text-slate-700 block">緊急聯絡人</span>
                <div class="grid grid-cols-3 gap-2">
                  <FormField :label="t('hr.employee.emergencyContact')">
                    <input v-model="editForm.emergency_contact_name" type="text" class="w-full px-2 py-1 text-xs rounded border border-slate-300" />
                  </FormField>
                  <FormField :label="t('hr.employee.emergencyRelationship')">
                    <input v-model="editForm.emergency_contact_relationship" type="text" class="w-full px-2 py-1 text-xs rounded border border-slate-300" />
                  </FormField>
                  <FormField :label="t('hr.employee.emergencyPhone')">
                    <input v-model="editForm.emergency_contact_phone" type="tel" class="w-full px-2 py-1 text-xs rounded border border-slate-300" />
                  </FormField>
                </div>
              </div>

              <div class="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  @click="isEditing = false"
                  class="px-3 py-1.5 text-xs rounded border border-slate-300 hover:bg-slate-100 text-slate-600 transition"
                >
                  {{ t('actions.cancel') }}
                </button>
                <button
                  type="button"
                  @click="saveEdit"
                  :disabled="isSaving"
                  class="px-4 py-1.5 text-xs font-semibold rounded bg-(--color-primary) text-white hover:bg-primary-hover transition disabled:opacity-50"
                >
                  {{ isSaving ? t('status.loading') : t('actions.save') }}
                </button>
              </div>
            </div>
          </div>

          <!-- 3. 學歷背景 -->
          <div class="border border-slate-200 rounded-xl p-4 space-y-3">
            <h4 class="text-xs font-bold text-slate-700 flex items-center justify-between">
              <span class="flex items-center"><span class="mr-1.5">🎓</span> {{ t('hr.persons.modal.education') }}</span>
              <span v-if="employeeData.education_history?.length" class="text-[10px] text-slate-400 font-mono">
                {{ employeeData.education_history.length }} 筆記錄
              </span>
            </h4>
            <div v-if="employeeData.education_history && employeeData.education_history.length > 0" class="overflow-x-auto border border-slate-200 rounded-lg">
              <table class="w-full text-[11px] text-left">
                <thead class="bg-slate-50 text-slate-600 border-b border-slate-200">
                  <tr>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.schoolName') }}</th>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.major') }}</th>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.startYear') }} - {{ t('hr.persons.modal.endYear') }}</th>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.graduationStatus') }}</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="(edu, idx) in employeeData.education_history" :key="idx" class="hover:bg-slate-50/50">
                    <td class="px-3 py-2 font-medium text-slate-800">{{ edu.school_name || '-' }}</td>
                    <td class="px-3 py-2 text-slate-600">{{ edu.major || '-' }}</td>
                    <td class="px-3 py-2 font-mono text-slate-500">{{ edu.start_year || '-' }} ~ {{ edu.end_year || '-' }}</td>
                    <td class="px-3 py-2 text-slate-700">
                      <span class="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-medium">{{ edu.status || '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="text-center py-4 text-slate-400 text-xs italic bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
              {{ t('hr.employeeDetailModal.notSpecified') }}
            </div>
          </div>

          <!-- 4. 工作經歷 -->
          <div class="border border-slate-200 rounded-xl p-4 space-y-3">
            <h4 class="text-xs font-bold text-slate-700 flex items-center justify-between">
              <span class="flex items-center"><span class="mr-1.5">💼</span> {{ t('hr.persons.modal.workExperience') }}</span>
              <span v-if="employeeData.work_experience?.length" class="text-[10px] text-slate-400 font-mono">
                {{ employeeData.work_experience.length }} 筆記錄
              </span>
            </h4>
            <div v-if="employeeData.work_experience && employeeData.work_experience.length > 0" class="overflow-x-auto border border-slate-200 rounded-lg">
              <table class="w-full text-[11px] text-left">
                <thead class="bg-slate-50 text-slate-600 border-b border-slate-200">
                  <tr>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.companyName') }}</th>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.jobTitleHistory') }}</th>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.jobDesc') }}</th>
                    <th class="px-3 py-2 font-semibold">{{ t('hr.persons.modal.yearsOfService') }}</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="(exp, idx) in employeeData.work_experience" :key="idx" class="hover:bg-slate-50/50">
                    <td class="px-3 py-2 font-medium text-slate-800">{{ exp.company_name || '-' }}</td>
                    <td class="px-3 py-2 text-slate-600">{{ exp.job_title || '-' }}</td>
                    <td class="px-3 py-2 text-slate-500 max-w-xs truncate" :title="exp.job_description">{{ exp.job_description || '-' }}</td>
                    <td class="px-3 py-2 font-mono text-slate-700">
                      <span class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold">{{ exp.years_of_service ? exp.years_of_service + ' 年' : '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="text-center py-4 text-slate-400 text-xs italic bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
              {{ t('hr.employeeDetailModal.notSpecified') }}
            </div>
          </div>
        </div>
      </div>

      <!-- 底部關閉按鈕 -->
      <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/80 flex justify-end">
        <button
          @click="emit('close')"
          type="button"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 hover:bg-white text-slate-700 transition"
        >
          {{ t('actions.close') }}
        </button>
      </div>
    </div>
  </div>
</template>

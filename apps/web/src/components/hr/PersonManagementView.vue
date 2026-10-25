<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useTranslation } from 'i18next-vue';
import PersonModal from './PersonModal.vue';
import { apiFetch } from '../../utils/auth';

interface PersonItem {
  id: string;
  national_id: string | null;
  full_name: string;
  english_name: string | null;
  birth_date: string | null;
  gender: string;
  nationality: string | null;
  marital_status: string;
  personal_email: string | null;
  mobile_phone: string | null;
  residential_address: string | null;
  permanent_address: string | null;
  emergency_contact_name: string | null;
  emergency_contact_relationship: string | null;
  emergency_contact_phone: string | null;
  employments_count: number;
  current_companies: string[];
}

const emit = defineEmits<{
  (e: 'start-onboard', person: PersonItem): void;
}>();

const { t } = useTranslation();

const persons = ref<PersonItem[]>([]);
const isLoading = ref(false);
const searchKeyword = ref('');
const errorMessage = ref('');

// 彈窗狀態
const showPersonModal = ref(false);
const selectedPersonId = ref<string | null>(null);

async function fetchPersons() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const url = searchKeyword.value.trim()
      ? `/api/v1/hr/persons?keyword=${encodeURIComponent(searchKeyword.value.trim())}`
      : '/api/v1/hr/persons';
    const res = await apiFetch(url);
    if (res.ok) {
      persons.value = await res.json();
    } else {
      errorMessage.value = t('hr.persons.table.empty');
    }
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  selectedPersonId.value = null;
  showPersonModal.value = true;
}

function openEditModal(person: PersonItem) {
  selectedPersonId.value = person.id;
  showPersonModal.value = true;
}

function handleStartOnboard(person: PersonItem) {
  emit('start-onboard', person);
}

onMounted(() => {
  fetchPersons();
});
</script>

<template>
  <div class="space-y-4">
    <!-- 頂端說明與搜尋/操作列 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold text-slate-800 flex items-center">
          <span class="mr-2">🪪</span> {{ t('hr.persons.title') }}
        </h3>
        <p class="text-xs text-text-muted mt-0.5">
          {{ t('hr.persons.subtitle') }}
        </p>
      </div>

      <div class="flex items-center space-x-2">
        <div class="relative">
          <input
            v-model="searchKeyword"
            @keyup.enter="fetchPersons"
            type="text"
            :placeholder="t('hr.persons.searchPlaceholder')"
            class="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) w-56"
          />
          <span class="absolute left-2.5 top-2 text-slate-400 text-xs">🔍</span>
        </div>
        <button
          @click="fetchPersons"
          class="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 shadow-xs transition cursor-pointer"
        >
          {{ t('actions.search') }}
        </button>
        <button
          @click="openCreateModal"
          class="px-3.5 py-1.5 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer flex items-center"
        >
          <span class="mr-1">➕</span> {{ t('hr.persons.createBtn') }}
        </button>
      </div>
    </div>

    <!-- 錯誤提示 -->
    <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
      ⚠️ {{ errorMessage }}
    </div>

    <!-- 人員主檔表格 -->
    <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-700">
          <thead class="bg-slate-50 text-[11px] font-semibold text-slate-600 uppercase border-b border-slate-200">
            <tr>
              <th class="px-4 py-3">{{ t('hr.persons.table.fullName') }}</th>
              <th class="px-4 py-3">{{ t('hr.persons.table.nationalId') }}</th>
              <th class="px-4 py-3">{{ t('hr.persons.table.genderBirth') }}</th>
              <th class="px-4 py-3">{{ t('hr.persons.table.nationality') }}</th>
              <th class="px-4 py-3">{{ t('hr.persons.table.personalPhone') }}</th>
              <th class="px-4 py-3">{{ t('hr.persons.table.personalEmail') }}</th>
              <th class="px-4 py-3 text-center">{{ t('hr.persons.table.employmentStatus') }}</th>
              <th class="px-4 py-3 text-right">{{ t('hr.persons.table.lifecycleActions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="isLoading">
              <td colspan="8" class="px-4 py-12 text-center text-slate-400">
                <span class="animate-spin inline-block mr-2">⏳</span> {{ t('hr.persons.table.loading') }}
              </td>
            </tr>
            <tr v-else-if="persons.length === 0">
              <td colspan="8" class="px-4 py-12 text-center text-slate-400">
                {{ t('hr.persons.table.empty') }}
              </td>
            </tr>
            <tr v-for="person in persons" :key="person.id" class="hover:bg-slate-50/60 transition">
              <td class="px-4 py-3">
                <div class="font-bold text-slate-900">{{ person.full_name }}</div>
                <div v-if="person.english_name" class="text-[11px] text-slate-400 font-normal">
                  {{ person.english_name }}
                </div>
              </td>
              <td class="px-4 py-3 font-mono font-medium text-slate-800">
                {{ person.national_id || '-' }}
              </td>
              <td class="px-4 py-3 text-slate-600">
                <span>{{ person.gender === 'MALE' ? t('hr.genders.shortMale') : person.gender === 'FEMALE' ? t('hr.genders.shortFemale') : '-' }}</span>
                <span v-if="person.birth_date" class="ml-1 text-slate-400 font-mono">({{ person.birth_date }})</span>
              </td>
              <td class="px-4 py-3 text-slate-600">
                <span class="px-2 py-0.5 rounded bg-slate-100 text-[10px] font-mono text-slate-700">
                  {{ person.nationality || 'TW' }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-slate-700">
                {{ person.mobile_phone || '-' }}
              </td>
              <td class="px-4 py-3 font-mono text-slate-600 text-[11px]">
                {{ person.personal_email || '-' }}
              </td>
              <td class="px-4 py-3 text-center">
                <div v-if="person.current_companies.length > 0" class="flex flex-wrap gap-1 justify-center">
                  <span
                    v-for="comp in person.current_companies"
                    :key="comp"
                    class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono"
                  >
                    {{ t('hr.persons.table.activeIn', { company: comp }) }}
                  </span>
                </div>
                <span v-else class="text-[11px] text-slate-400 italic">
                  {{ t('hr.persons.table.notEmployed') }}
                </span>
              </td>
              <td class="px-4 py-3 text-right space-x-1.5 whitespace-nowrap">
                <button
                  @click="openEditModal(person)"
                  class="px-2.5 py-1 text-[11px] font-medium rounded border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 transition cursor-pointer"
                  :title="t('hr.persons.table.editPerson')"
                >
                  ✏️ {{ t('hr.persons.table.editPerson') }}
                </button>
                <button
                  @click="handleStartOnboard(person)"
                  class="px-2.5 py-1 text-[11px] font-semibold rounded bg-sky-600 hover:bg-sky-700 text-white shadow-xs transition cursor-pointer"
                  :title="t('hr.persons.table.startOnboard')"
                >
                  📝 {{ t('hr.persons.table.startOnboard') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 人員新增/編輯彈窗 -->
    <PersonModal
      :isOpen="showPersonModal"
      :personId="selectedPersonId"
      @close="showPersonModal = false"
      @saved="fetchPersons"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { apiFetch } from '../../utils/auth';
import { fetchAvailableCompanies } from '../../utils/companies';

interface CompanyItem {
  id: string;
  name: string;
  tax_id: string | null;
  representative_name: string | null;
  registered_address: string | null;
  contact_phone: string | null;
  default_timezone: string;
  default_currency: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

const emit = defineEmits<{
  (e: 'updated'): void;
}>();

const { t } = useTranslation();

const companies = ref<CompanyItem[]>([]);
const isLoading = ref(false);
const errorMessage = ref('');

// 編輯 / 新增 Modal 控制
const showModal = ref(false);
const isEditing = ref(false);
const isSaving = ref(false);
const modalError = ref('');

const form = ref<{
  id: string;
  name: string;
  tax_id: string;
  representative_name: string;
  registered_address: string;
  contact_phone: string;
  default_timezone: string;
  default_currency: string;
  is_active: boolean;
}>({
  id: '',
  name: '',
  tax_id: '',
  representative_name: '',
  registered_address: '',
  contact_phone: '',
  default_timezone: 'Asia/Taipei',
  default_currency: 'TWD',
  is_active: true,
});

async function fetchCompanies() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const res = await apiFetch('/api/v1/hr/companies');
    if (res.ok) {
      companies.value = await res.json();
    } else {
      errorMessage.value = '讀取公司列表失敗';
    }
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  isEditing.value = false;
  modalError.value = '';
  form.value = {
    id: '',
    name: '',
    tax_id: '',
    representative_name: '',
    registered_address: '',
    contact_phone: '',
    default_timezone: 'Asia/Taipei',
    default_currency: 'TWD',
    is_active: true,
  };
  showModal.value = true;
}

function openEditModal(comp: CompanyItem) {
  isEditing.value = true;
  modalError.value = '';
  form.value = {
    id: comp.id,
    name: comp.name,
    tax_id: comp.tax_id || '',
    representative_name: comp.representative_name || '',
    registered_address: comp.registered_address || '',
    contact_phone: comp.contact_phone || '',
    default_timezone: comp.default_timezone,
    default_currency: comp.default_currency,
    is_active: comp.is_active,
  };
  showModal.value = true;
}

async function saveCompany() {
  if (!form.value.name) {
    modalError.value = '公司法定名稱為必填項目';
    return;
  }
  if (!isEditing.value && !form.value.id) {
    modalError.value = '公司代碼為必填項目';
    return;
  }

  isSaving.value = true;
  modalError.value = '';

  try {
    const url = isEditing.value
      ? `/api/v1/hr/companies/${form.value.id}`
      : '/api/v1/hr/companies';
    const method = isEditing.value ? 'PUT' : 'POST';

    const payload = isEditing.value
      ? {
          name: form.value.name,
          tax_id: form.value.tax_id || null,
          representative_name: form.value.representative_name || null,
          registered_address: form.value.registered_address || null,
          contact_phone: form.value.contact_phone || null,
          default_timezone: form.value.default_timezone,
          default_currency: form.value.default_currency,
          is_active: form.value.is_active,
        }
      : {
          id: form.value.id,
          name: form.value.name,
          tax_id: form.value.tax_id || null,
          representative_name: form.value.representative_name || null,
          registered_address: form.value.registered_address || null,
          contact_phone: form.value.contact_phone || null,
          default_timezone: form.value.default_timezone,
          default_currency: form.value.default_currency,
        };

    const res = await apiFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error?.message || '儲存公司基本資料失敗');
    }

    showModal.value = false;
    await fetchCompanies();
    await fetchAvailableCompanies();
    emit('updated');
  } catch (err: any) {
    modalError.value = err.message || '儲存過程發生錯誤';
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  fetchCompanies();
});
</script>

<template>
  <div class="space-y-5">
    <!-- 頂端操作列 -->
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-semibold text-slate-800">
          {{ t('hr.company.pageTitle') }}
        </h3>
        <p class="text-xs text-text-muted">
          {{ t('hr.company.pageSubtitle') }}
        </p>
      </div>
      <button
        type="button"
        @click="openCreateModal"
        class="px-3.5 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer flex items-center space-x-1"
      >
        <span>🏢</span>
        <span>{{ t('hr.company.createBtn') }}</span>
      </button>
    </div>

    <!-- 載入與錯誤狀態 -->
    <div v-if="isLoading" class="py-12 text-center text-xs text-slate-500">
      <span class="animate-spin inline-block mr-2">⏳</span> {{ t('status.loading') }}
    </div>

    <div v-else-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
      ⚠️ {{ errorMessage }}
    </div>

    <!-- 公司卡片 Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-5">
      <div
        v-for="comp in companies"
        :key="comp.id"
        class="bg-white rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition-all p-5 flex flex-col justify-between space-y-4 relative overflow-hidden"
      >
        <!-- 頂端狀態與代碼 -->
        <div class="flex items-start justify-between">
          <div class="flex items-center space-x-3">
            <div class="w-11 h-11 rounded-xl bg-linear-to-br from-blue-500 to-indigo-600 text-white font-bold text-base flex items-center justify-center shadow-xs">
              {{ comp.id.replace('ETJ-', '') }}
            </div>
            <div>
              <div class="flex items-center space-x-2">
                <h4 class="text-base font-bold text-slate-900 leading-snug">
                  {{ comp.name }}
                </h4>
                <span
                  :class="[
                    'px-2 py-0.5 text-[10px] font-semibold rounded-full',
                    comp.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'
                  ]"
                >
                  {{ comp.is_active ? t('hr.company.active') : t('hr.company.inactive') }}
                </span>
              </div>
              <p class="text-xs font-mono font-semibold text-blue-600 mt-0.5">
                {{ comp.id }}
              </p>
            </div>
          </div>

          <button
            type="button"
            @click="openEditModal(comp)"
            class="px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 transition cursor-pointer"
          >
            ✏️ {{ t('hr.company.editBtn') }}
          </button>
        </div>

        <!-- 詳細規格資訊區 -->
        <div class="grid grid-cols-2 gap-3 text-xs pt-2 border-t border-slate-100">
          <div>
            <span class="text-slate-400 block text-[11px]">{{ t('hr.company.taxId') }}</span>
            <span class="font-mono text-slate-800 font-medium">{{ comp.tax_id || t('hr.company.notSet') }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[11px]">{{ t('hr.company.representative') }}</span>
            <span class="text-slate-800 font-medium">{{ comp.representative_name || t('hr.company.notSet') }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[11px]">{{ t('hr.company.phone') }}</span>
            <span class="font-mono text-slate-800">{{ comp.contact_phone || t('hr.company.notSet') }}</span>
          </div>
          <div>
            <span class="text-slate-400 block text-[11px]">{{ t('hr.company.timezone') }} / {{ t('hr.company.currency') }}</span>
            <span class="font-mono text-slate-800 font-medium">{{ comp.default_timezone }} ({{ comp.default_currency }})</span>
          </div>
          <div class="col-span-2">
            <span class="text-slate-400 block text-[11px]">{{ t('hr.company.address') }}</span>
            <span class="text-slate-800">{{ comp.registered_address || t('hr.company.notSetAddress') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 編輯 / 新增對話框 -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-fade-in"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        <!-- 標題列 -->
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <h3 class="text-base font-semibold text-slate-800 flex items-center">
            <span class="mr-2">🏢</span>
            {{ isEditing ? t('hr.company.editTitle') : t('hr.company.createTitle') }}
          </h3>
          <button
            @click="showModal = false"
            class="text-slate-400 hover:text-slate-600 text-xl leading-none cursor-pointer"
          >
            &times;
          </button>
        </div>

        <!-- 表單本體 -->
        <div class="p-6 overflow-y-auto space-y-4 flex-1">
          <div v-if="modalError" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            ⚠️ {{ modalError }}
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.company.id')" required>
              <input
                v-model="form.id"
                type="text"
                :disabled="isEditing"
                :placeholder="t('hr.company.idPlaceholder')"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono disabled:bg-slate-100 disabled:text-slate-500"
              />
            </FormField>

            <FormField :label="t('hr.company.name')" required>
              <input
                v-model="form.name"
                type="text"
                :placeholder="t('hr.company.namePlaceholder')"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-medium"
              />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.company.taxId')">
              <input
                v-model="form.tax_id"
                type="text"
                placeholder="例如 80123456"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
              />
            </FormField>

            <FormField :label="t('hr.company.representative')">
              <input
                v-model="form.representative_name"
                type="text"
                placeholder="代表人姓名"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <FormField :label="t('hr.company.phone')">
            <input
              v-model="form.contact_phone"
              type="tel"
              placeholder="例如 +886-2-2345-6789"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) font-mono"
            />
          </FormField>

          <FormField :label="t('hr.company.address')">
            <input
              v-model="form.registered_address"
              type="text"
              placeholder="登記法定通訊地址"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            />
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.company.timezone')" required>
              <select
                v-model="form.default_timezone"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
              >
                <option value="Asia/Taipei">台北 (Asia/Taipei, UTC+8)</option>
                <option value="Asia/Tokyo">東京 (Asia/Tokyo, UTC+9)</option>
              </select>
            </FormField>

            <FormField :label="t('hr.company.currency')" required>
              <select
                v-model="form.default_currency"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
              >
                <option value="TWD">新台幣 (TWD)</option>
                <option value="JPY">日圓 (JPY)</option>
                <option value="USD">美元 (USD)</option>
              </select>
            </FormField>
          </div>

          <div v-if="isEditing" class="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input
                v-model="form.is_active"
                type="checkbox"
                class="w-4 h-4 rounded text-(--color-primary) focus:ring-0"
              />
              <span class="text-xs font-semibold text-slate-800">啟用該公司營運狀態</span>
            </label>
          </div>
        </div>

        <!-- 底部按鈕 -->
        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/80 flex justify-end space-x-2">
          <button
            type="button"
            @click="showModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 hover:bg-white text-slate-700 transition cursor-pointer"
          >
            {{ t('actions.cancel') }}
          </button>
          <button
            type="button"
            @click="saveCompany"
            :disabled="isSaving"
            class="px-5 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs transition disabled:opacity-50 cursor-pointer"
          >
            {{ isSaving ? t('status.loading') : t('actions.submit') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

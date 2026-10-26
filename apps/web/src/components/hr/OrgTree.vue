<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import DateTimeInput from '../common/DateTimeInput.vue';
import { apiFetch } from '../../utils/auth';
import { availableCompanies, fetchAvailableCompanies } from '../../utils/companies';

interface OrgItem {
  id: string;
  company_id: string;
  code: string;
  name: string;
  parent_id: string | null;
  level: string;
  manager_id?: string | null;
  manager_name?: string | null;
  manager_no?: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  is_active: boolean;
}

const props = defineProps<{
  companyId: string;
}>();

const { t } = useTranslation();

const selectedCompanyId = ref<string>(props.companyId || 'ETJ-TW');
const allOrganizations = ref<OrgItem[]>([]);
const isLoading = ref(false);
const isSaving = ref(false);
const showModal = ref(false);
const isEditing = ref(false);
const editingOrgId = ref('');

const formCompanyId = ref('ETJ-TW');
const formOrgId = ref('');
const formCode = ref('');
const formName = ref('');
const formParentId = ref('');
const formLevel = ref('DEPARTMENT');
const formManagerId = ref('');
const formEffectiveDate = ref('');
const formExpiryDate = ref('');
const formIsActive = ref(true);
const errorMessage = ref('');

const companyEmployees = ref<Array<{ id: string; employee_no: string; full_name: string; status?: string }>>([]);

async function fetchCompanyEmployees(companyId: string) {
  if (!companyId) {
    companyEmployees.value = [];
    return;
  }
  try {
    const res = await apiFetch(`/api/v1/hr/employees?company_id=${companyId}`);
    if (res.ok) {
      const data = await res.json();
      companyEmployees.value = data.filter((e: any) => e.status !== 'RESIGNED');
    }
  } catch {
    companyEmployees.value = [];
  }
}

const orgLevels = [
  { value: 'TEAM', key: 'team', label: '組 (Team)' },
  { value: 'SECTION', key: 'section', label: '課 (Section)' },
  { value: 'DEPARTMENT', key: 'department', label: '部 (Department)' },
  { value: 'DIVISION', key: 'division', label: '處 (Division)' },
  { value: 'CENTER', key: 'center', label: '中心 (Center)' },
  { value: 'GM', key: 'gm', label: '總經理 (General Manager)' },
  { value: 'CEO', key: 'ceo', label: '執行長 (CEO)' },
  { value: 'CHAIRMAN', key: 'chairman', label: '董事長 (Chairman)' },
] as const;

function formatLevel(level: string): string {
  const found = orgLevels.find(o => o.value === level);
  if (found) {
    return t(`hr.org.levels.${found.key}`, found.label);
  }
  if (level === 'GENERAL_MANAGER') {
    return t('hr.org.levels.gm', '總經理 (General Manager)');
  }
  return level;
}

function getCompanyName(companyId: string): string {
  const comp = availableCompanies.value.find(c => c.id === companyId);
  return comp ? comp.name : companyId;
}

// 依當前選擇公司過濾之組織卡片
const displayedOrganizations = computed(() => {
  if (!selectedCompanyId.value || selectedCompanyId.value === 'ALL') {
    return allOrganizations.value;
  }
  return allOrganizations.value.filter(o => o.company_id === selectedCompanyId.value);
});

// 上級組織候選清單：嚴格限制與 formCompanyId 同一公司，防止跨公司上級閉環或外鍵衝突
const parentOrgOptions = computed(() => {
  return allOrganizations.value.filter(o =>
    o.company_id === formCompanyId.value &&
    (!isEditing.value || o.id !== editingOrgId.value)
  );
});

async function fetchOrgs() {
  isLoading.value = true;
  try {
    const res = await apiFetch('/api/v1/hr/organizations');
    if (res.ok) {
      allOrganizations.value = await res.json();
    }
  } catch {
    allOrganizations.value = [];
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  isEditing.value = false;
  editingOrgId.value = '';
  formCompanyId.value = selectedCompanyId.value !== 'ALL' ? selectedCompanyId.value : (props.companyId || 'ETJ-TW');
  formOrgId.value = '';
  formCode.value = '';
  formName.value = '';
  formParentId.value = '';
  formLevel.value = 'DEPARTMENT';
  formManagerId.value = '';
  formEffectiveDate.value = new Date().toISOString().split('T')[0];
  formExpiryDate.value = '';
  formIsActive.value = true;
  errorMessage.value = '';
  fetchCompanyEmployees(formCompanyId.value);
  showModal.value = true;
}

function openEditModal(org: OrgItem) {
  isEditing.value = true;
  editingOrgId.value = org.id;
  formCompanyId.value = org.company_id;
  formOrgId.value = org.id;
  formCode.value = org.code;
  formName.value = org.name;
  formParentId.value = org.parent_id || '';
  formLevel.value = org.level;
  formManagerId.value = org.manager_id || '';
  formEffectiveDate.value = org.effective_date || '';
  formExpiryDate.value = org.expiry_date || '';
  formIsActive.value = org.is_active;
  errorMessage.value = '';
  fetchCompanyEmployees(formCompanyId.value);
  showModal.value = true;
}

async function saveOrg() {
  if (!formCompanyId.value) {
    errorMessage.value = t('hr.org.selectCompany', '請選擇所屬公司 (Please select company)');
    return;
  }

  if (!formCode.value || !formName.value || (!isEditing.value && !formOrgId.value)) {
    errorMessage.value = t('hr.org.requiredFields', '請填寫代碼與名稱');
    return;
  }

  if (formEffectiveDate.value && formExpiryDate.value && formEffectiveDate.value > formExpiryDate.value) {
    errorMessage.value = '失效日期不可早於有效起始日 (Expiry date cannot be earlier than effective date)';
    return;
  }

  errorMessage.value = '';
  isSaving.value = true;

  try {
    let res: Response;
    if (isEditing.value) {
      res = await apiFetch(`/api/v1/hr/organizations/${editingOrgId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: formCode.value,
          name: formName.value,
          parent_id: formParentId.value || null,
          level: formLevel.value,
          manager_id: formManagerId.value || null,
          effective_date: formEffectiveDate.value || null,
          expiry_date: formExpiryDate.value || null,
          is_active: formIsActive.value,
        }),
      });
    } else {
      res = await apiFetch('/api/v1/hr/organizations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: formOrgId.value,
          company_id: formCompanyId.value,
          code: formCode.value,
          name: formName.value,
          parent_id: formParentId.value || null,
          level: formLevel.value,
          manager_id: formManagerId.value || null,
          effective_date: formEffectiveDate.value || null,
          expiry_date: formExpiryDate.value || null,
        }),
      });
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.detail || '儲存部門失敗');
    }

    // 若新建立的部門所屬公司與當前畫面選擇不同，自動切換至該公司以利即時檢視
    if (selectedCompanyId.value !== 'ALL' && selectedCompanyId.value !== formCompanyId.value) {
      selectedCompanyId.value = formCompanyId.value;
    }

    showModal.value = false;
    await fetchOrgs();
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSaving.value = false;
  }
}

watch(
  () => props.companyId,
  (newId) => {
    if (newId) {
      selectedCompanyId.value = newId;
    }
  }
);

onMounted(async () => {
  await fetchAvailableCompanies();
  await fetchOrgs();
});
</script>

<template>
  <div class="space-y-4">
    <!-- 頂端控制列：標題、所屬公司篩選與新增按鈕 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-border-main shadow-2xs">
      <div>
        <h3 class="text-sm font-semibold text-slate-800 flex items-center space-x-1.5">
          <span>🏢</span>
          <span>{{ t('hr.org.title', '部門組織階層 (DAG 無循環驗證)') }}</span>
        </h3>
        <p class="text-xs text-text-muted mt-0.5">
          {{ t('hr.org.subtitle', '檢視與維護公司組織架構，嚴格禁止父子層級相互依賴或閉環') }}
        </p>
      </div>

      <div class="flex items-center space-x-3">
        <!-- 公司快速切換選單 -->
        <div class="flex items-center space-x-1.5">
          <span class="text-xs font-medium text-slate-500 whitespace-nowrap">{{ t('hr.org.company', '所屬公司') }}:</span>
          <select
            v-model="selectedCompanyId"
            class="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white font-medium text-slate-700 shadow-2xs focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
          >
            <option value="ALL">{{ t('hr.org.allCompanies', '全部公司部門') }}</option>
            <option v-for="c in availableCompanies" :key="c.id" :value="c.id">
              {{ c.name }} ({{ c.id }})
            </option>
          </select>
        </div>

        <button
          @click="openCreateModal"
          class="px-3.5 py-1.5 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer whitespace-nowrap"
        >
          {{ t('hr.org.createBtn', '+ 新增組織部門') }}
        </button>
      </div>
    </div>

    <!-- 組織清單卡片 -->
    <div v-if="isLoading" class="text-xs text-text-muted py-6 text-center">
      {{ t('status.loading', '載入中...') }}
    </div>
    <div v-else-if="displayedOrganizations.length === 0" class="text-xs text-text-muted py-8 text-center bg-white rounded-xl border border-border-main">
      {{ t('hr.org.noData', '尚無組織部門資料') }}
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="org in displayedOrganizations"
        :key="org.id"
        class="bg-white p-4 rounded-xl border border-border-main shadow-xs hover:border-(--color-primary) transition flex flex-col justify-between"
      >
        <div>
          <!-- 所屬公司標記列 -->
          <div class="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 text-[11px]">
            <div class="flex items-center space-x-1 text-slate-600 font-medium">
              <span>🏢</span>
              <span>{{ getCompanyName(org.company_id) }}</span>
              <span class="font-mono text-slate-400 text-[10px]">({{ org.company_id }})</span>
            </div>
            <span
              class="text-[10px] font-semibold px-1.5 py-0.2 rounded"
              :class="org.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-500 border border-slate-200'"
            >
              {{ org.is_active ? t('hr.org.active') : t('hr.org.inactive') }}
            </span>
          </div>

          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-slate-800">{{ org.name }}</span>
            <div class="flex items-center space-x-1.5">
              <span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
                {{ formatLevel(org.level) }}
              </span>
              <button
                @click="openEditModal(org)"
                class="px-2 py-0.5 text-[11px] font-medium text-slate-600 hover:text-(--color-primary) hover:bg-slate-50 border border-slate-200 rounded transition cursor-pointer"
              >
                ✏️ {{ t('hr.org.editBtn') }}
              </button>
            </div>
          </div>

          <div class="text-[11px] text-text-muted space-y-1">
            <p>{{ t('hr.org.code') }}: <span class="font-mono text-slate-700 font-medium">{{ org.code }}</span></p>
            <p>{{ t('hr.org.id') }}: <span class="font-mono text-slate-700">{{ org.id }}</span></p>
            <p v-if="org.parent_id">
              {{ t('hr.org.parent') }}: <span class="font-mono font-medium text-slate-700">{{ org.parent_id }}</span>
            </p>
            <p v-else class="text-emerald-600 font-medium">{{ t('hr.org.rootDept') }}</p>
            <p v-if="org.manager_name">
              {{ t('hr.org.manager', '部門主管') }}: <span class="font-medium text-slate-800">👤 {{ org.manager_name }}</span> <span v-if="org.manager_no" class="font-mono text-slate-500 text-[10px]">({{ org.manager_no }})</span>
            </p>
            
            <!-- 有效與失效日期 -->
            <div class="pt-2 mt-2 border-t border-slate-100 flex items-center justify-between text-[10px]">
              <span class="text-slate-500">{{ t('hr.ledger.validPeriod') }}:</span>
              <span class="font-mono text-slate-700">
                {{ org.effective_date || '—' }} ~ {{ org.expiry_date || t('hr.org.permanent') }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增 / 編輯組織 Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">
            {{ isEditing ? t('hr.org.editTitle', '編輯組織部門') : t('hr.org.createTitle', '+ 新增組織部門') }}
          </h3>
          <button @click="showModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <!-- 所屬公司綁定欄位 -->
          <FormField :label="t('hr.org.company', '所屬公司 (Company)')" :required="!isEditing" :hint="isEditing ? t('hr.org.companyImmutable', '所屬公司（建立後不可任意跨公司異動）') : undefined">
            <select
              v-if="!isEditing"
              v-model="formCompanyId"
              @change="formParentId = ''; fetchCompanyEmployees(formCompanyId); formManagerId = ''"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            >
              <option
                v-for="c in availableCompanies"
                :key="c.id"
                :value="c.id"
              >
                {{ c.name }} ({{ c.id }})
              </option>
            </select>
            <input
              v-else
              :value="`${getCompanyName(formCompanyId)} (${formCompanyId})`"
              type="text"
              disabled
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 bg-slate-100 text-slate-600 font-medium cursor-not-allowed"
            />
          </FormField>

          <FormField :label="t('hr.org.id', '組織識別碼 (ID)')" :required="!isEditing" hint="例如 ORG-RD-01">
            <input
              v-model="formOrgId"
              type="text"
              :disabled="isEditing"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) disabled:bg-slate-100 disabled:text-slate-500"
            />
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.org.code', '部門代號 (Code)')" required>
              <input
                v-model="formCode"
                type="text"
                placeholder="例如 RD"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
            <FormField :label="t('hr.org.name', '部門名稱')" required>
              <input
                v-model="formName"
                type="text"
                placeholder="例如 研發處"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.org.level', '組織層級')">
              <select
                v-model="formLevel"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              >
                <option
                  v-for="lvl in orgLevels"
                  :key="lvl.value"
                  :value="lvl.value"
                >
                  {{ t(`hr.org.levels.${lvl.key}`, lvl.label) }}
                </option>
              </select>
            </FormField>

            <FormField :label="t('hr.org.parent', '上級組織 (可為空)')">
              <select
                v-model="formParentId"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              >
                <option value="">{{ t('hr.org.noParent', '無 (為頂層根組織)') }}</option>
                <option
                  v-for="org in parentOrgOptions"
                  :key="org.id"
                  :value="org.id"
                >
                  {{ org.name }} ({{ org.code }})
                </option>
              </select>
            </FormField>
          </div>

          <!-- 部門主管 -->
          <FormField :label="t('hr.org.manager', '部門主管 (Department Manager)')" hint="選填，負責該部門之簽核與管理">
            <select
              v-model="formManagerId"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            >
              <option value="">{{ t('hr.org.noManager', '無 (未指定主管)') }}</option>
              <option
                v-for="emp in companyEmployees"
                :key="emp.id"
                :value="emp.id"
              >
                {{ emp.employee_no }} - {{ emp.full_name }}
              </option>
            </select>
          </FormField>

          <!-- 有效日期與失效日期 -->
          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.org.effectiveDate', '有效起始日')">
              <DateTimeInput
                v-model="formEffectiveDate"
                mode="date"
              />
            </FormField>
            <FormField :label="t('hr.org.expiryDate', '失效截止日')" hint="留空代表永久有效">
              <DateTimeInput
                v-model="formExpiryDate"
                mode="date"
              />
            </FormField>
          </div>

          <!-- 啟用狀態 (僅編輯時或皆可切換) -->
          <div v-if="isEditing" class="pt-2 flex items-center justify-between border-t border-slate-100">
            <span class="text-xs font-medium text-slate-700">{{ t('hr.org.activeStatus', '啟用狀態') }}</span>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="formIsActive" class="sr-only peer" />
              <div class="w-9 h-5 bg-slate-200 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-(--color-primary)"></div>
              <span class="ml-2 text-xs font-semibold text-slate-600">
                {{ formIsActive ? t('hr.org.active', '啟用') : t('hr.org.inactive', '停用') }}
              </span>
            </label>
          </div>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            {{ t('hr.org.cancel', '取消') }}
          </button>
          <button
            @click="saveOrg"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer disabled:opacity-50"
          >
            {{ isSaving ? t('status.loading', '儲存中...') : t('hr.org.save', '儲存') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

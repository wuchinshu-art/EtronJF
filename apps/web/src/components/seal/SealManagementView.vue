<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import StatusBadge from '../common/StatusBadge.vue';
import { apiFetch, currentUser } from '../../utils/auth';

const props = defineProps<{
  companyId: string;
  timezone: string;
}>();

const { t } = useTranslation();

interface SealItem {
  id: string;
  company_id: string;
  code: string;
  name: string;
  seal_type: string;
  custodian_employee_id: string;
  custodian_name?: string;
  custodian_employee_no?: string;
  is_active: boolean;
  effective_from: string;
  effective_to?: string | null;
}

interface EmployeeOption {
  id: string;
  employee_no: string;
  full_name: string;
}

interface SealRequestItem {
  id: string;
  request_number: string;
  document_name: string;
  seal_id: string;
  copies: number;
  status: string;
  execution_status: string;
  created_at: string;
}

const activeTab = ref<'requests' | 'seals'>('requests');
const requests = ref<SealRequestItem[]>([]);
const seals = ref<SealItem[]>([]);
const employees = ref<EmployeeOption[]>([]);
const isLoading = ref(false);

// 新增印鑑主檔 Modal 狀態
const showCreateSealModal = ref(false);
const newSealCode = ref('');
const newSealName = ref('');
const newSealType = ref('COMPANY_SEAL');
const newCustodianId = ref('');
const newEffectiveFrom = ref(new Date().toISOString().split('T')[0]);
const newEffectiveTo = ref('');
const isSavingSeal = ref(false);
const sealErrorMessage = ref('');

const sealTypeOptions = [
  { value: 'COMPANY_SEAL', labelKey: 'sealView.sealTypes.COMPANY_SEAL' },
  { value: 'LEGAL_REP', labelKey: 'sealView.sealTypes.LEGAL_REP' },
  { value: 'CONTRACT_SEAL', labelKey: 'sealView.sealTypes.CONTRACT_SEAL' },
  { value: 'FINANCE_SEAL', labelKey: 'sealView.sealTypes.FINANCE_SEAL' },
  { value: 'DEPARTMENT_SEAL', labelKey: 'sealView.sealTypes.DEPARTMENT_SEAL' },
  { value: 'OTHER', labelKey: 'sealView.sealTypes.OTHER' },
];

// 新建用印申請 Modal
const showCreateModal = ref(false);
const selectedSealId = ref('');
const documentName = ref('');
const purpose = ref('');
const copies = ref(1);
const documentVersion = ref('v1.0');
const isSaving = ref(false);
const errorMessage = ref('');

// 執行用印 Modal
const showExecuteModal = ref(false);
const executingRequestId = ref('');
const sealedCopies = ref(1);
const finalScanUrl = ref('https://storage.etron.com/docs/sealed_final.pdf');

async function fetchData() {
  isLoading.value = true;
  try {
    const [reqsRes, sealsRes, empsRes] = await Promise.all([
      apiFetch(`/api/v1/seal/requests?company_id=${props.companyId}`),
      apiFetch(`/api/v1/seals?company_id=${props.companyId}`),
      apiFetch(`/api/v1/hr/employees?company_id=${props.companyId}`),
    ]);

    if (reqsRes.ok) requests.value = await reqsRes.json();
    if (sealsRes.ok) seals.value = await sealsRes.json();
    if (empsRes.ok) employees.value = await empsRes.json();
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

function openCreateSealModal() {
  newSealCode.value = `SEAL-${props.companyId}-${Date.now().toString().slice(-4)}`;
  newSealName.value = '';
  newSealType.value = 'COMPANY_SEAL';
  newCustodianId.value = employees.value[0]?.id || currentUser.value?.employee_id || '';
  newEffectiveFrom.value = new Date().toISOString().split('T')[0];
  newEffectiveTo.value = '';
  sealErrorMessage.value = '';
  showCreateSealModal.value = true;
}

async function saveNewSeal() {
  if (!newSealCode.value.trim() || !newSealName.value.trim() || !newCustodianId.value || !newEffectiveFrom.value) {
    sealErrorMessage.value = '請填寫印鑑代號、印鑑名稱、保管人員工與生效起日';
    return;
  }

  isSavingSeal.value = true;
  sealErrorMessage.value = '';

  try {
    const res = await apiFetch('/api/v1/seals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        code: newSealCode.value.trim(),
        name: newSealName.value.trim(),
        seal_type: newSealType.value,
        custodian_employee_id: newCustodianId.value,
        effective_from: newEffectiveFrom.value,
        effective_to: newEffectiveTo.value || null,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '建立印鑑失敗');
    }

    showCreateSealModal.value = false;
    await fetchData();
  } catch (err: any) {
    sealErrorMessage.value = err.message || '連線錯誤';
  } finally {
    isSavingSeal.value = false;
  }
}

function openCreateModal() {
  selectedSealId.value = seals.value[0]?.id || 'SEAL-TW-CORP';
  documentName.value = '台日營運策略合作意向協議書';
  purpose.value = '業務合作簽署法定正式印鑑用印';
  copies.value = 2;
  documentVersion.value = 'v1.0';
  errorMessage.value = '';
  showCreateModal.value = true;
}

async function saveSealRequest(andSubmit: boolean = false) {
  if (!selectedSealId.value || !documentName.value || !purpose.value) {
    errorMessage.value = '請填寫印鑑選擇、文件名稱與用印用途';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const res = await apiFetch('/api/v1/seal/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: currentUser.value?.employee_id || 'EMP-DEFAULT',
        seal_id: selectedSealId.value,
        document_name: documentName.value,
        purpose: purpose.value,
        copies: Number(copies.value),
        document_version: documentVersion.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '建立用印申請失敗');
    }

    const created = await res.json();
    if (andSubmit && created.request_id) {
      const submitRes = await apiFetch(`/api/v1/seal/requests/${created.request_id}/submit`, {
        method: 'POST',
      });
      if (!submitRes.ok) {
        const err = await submitRes.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '用印申請建立成功，但送審失敗');
      }
    }

    showCreateModal.value = false;
    await fetchData();
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSaving.value = false;
  }
}

async function submitSingleRequest(id: string) {
  try {
    const res = await apiFetch(`/api/v1/seal/requests/${id}/submit`, { method: 'POST' });
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

function openExecuteModal(id: string, reqCopies: number) {
  executingRequestId.value = id;
  sealedCopies.value = reqCopies;
  showExecuteModal.value = true;
}

async function doExecuteSeal() {
  isSaving.value = true;
  try {
    const res = await apiFetch(`/api/v1/seal/requests/${executingRequestId.value}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sealed_copies: Number(sealedCopies.value),
        final_sealed_document_url: finalScanUrl.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || '執行用印登記失敗');
    }

    showExecuteModal.value = false;
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
        <h2 class="text-base font-bold text-slate-800">🔏 {{ t('sealView.title') }}</h2>
        <p class="text-xs text-text-muted">{{ t('sealView.subtitle') }}</p>
      </div>
      <button
        v-if="activeTab === 'requests'"
        @click="openCreateModal"
        class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
      >
        {{ t('sealView.createRequest') }}
      </button>
      <button
        v-else
        @click="openCreateSealModal"
        class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer flex items-center space-x-1.5"
      >
        <span>🔏</span>
        <span>{{ t('sealView.createSeal') }}</span>
      </button>
    </div>

    <!-- 頁籤導航 -->
    <div class="flex space-x-2 border-b border-border-main">
      <button
        @click="activeTab = 'requests'"
        class="px-4 py-2 text-xs font-semibold border-b-2 transition cursor-pointer"
        :class="activeTab === 'requests' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
      >
        📑 {{ t('sealView.tabs.requests') }} ({{ requests.length }})
      </button>
      <button
        @click="activeTab = 'seals'"
        class="px-4 py-2 text-xs font-semibold border-b-2 transition cursor-pointer"
        :class="activeTab === 'seals' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
      >
        🔏 {{ t('sealView.tabs.seals') }} ({{ seals.length }})
      </button>
    </div>

    <!-- 用印申請單清單 -->
    <div v-if="activeTab === 'requests'" class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="requests.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('sealView.noRequests') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('sealView.requestsTable.requestNo') }}</th>
              <th class="px-4 py-3">{{ t('sealView.requestsTable.docName') }}</th>
              <th class="px-4 py-3">{{ t('sealView.requestsTable.sealCode') }}</th>
              <th class="px-4 py-3">{{ t('sealView.requestsTable.copies') }}</th>
              <th class="px-4 py-3">{{ t('sealView.requestsTable.approvalStatus') }}</th>
              <th class="px-4 py-3">{{ t('sealView.requestsTable.executionStatus') }}</th>
              <th class="px-4 py-3 text-right">{{ t('sealView.requestsTable.actions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="r in requests" :key="r.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ r.request_number }}</td>
              <td class="px-4 py-3 font-semibold text-slate-800">{{ r.document_name }}</td>
              <td class="px-4 py-3 font-mono text-slate-600">{{ r.seal_id }}</td>
              <td class="px-4 py-3 font-bold text-slate-700">{{ t('sealView.requestsTable.copiesUnit', { count: r.copies }) }}</td>
              <td class="px-4 py-3">
                <StatusBadge :status="r.status" />
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-semibold"
                  :class="r.execution_status === 'SEALED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'"
                >
                  {{ r.execution_status === 'SEALED' ? t('sealView.requestsTable.sealed') : t('sealView.requestsTable.pendingSeal') }}
                </span>
              </td>
              <td class="px-4 py-3 text-right space-x-2">
                <button
                  v-if="r.status === 'DRAFT'"
                  @click="submitSingleRequest(r.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded transition cursor-pointer"
                >
                  {{ t('sealView.requestsTable.submit') }}
                </button>
                <button
                  v-if="r.status === 'APPROVED' && r.execution_status === 'PENDING'"
                  @click="openExecuteModal(r.id, r.copies)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded transition cursor-pointer"
                >
                  🖋️ {{ t('sealView.requestsTable.markSealed') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 印鑑清冊 -->
    <div v-else class="space-y-4">
      <div v-if="seals.length === 0" class="p-12 text-center bg-white rounded-2xl border border-slate-200">
        <div class="text-3xl mb-2">🔏</div>
        <p class="text-xs text-text-muted mb-4">{{ t('sealView.sealsTable.empty') }}</p>
        <button
          @click="openCreateSealModal"
          class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
        >
          {{ t('sealView.createSeal') }}
        </button>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        <div
          v-for="s in seals"
          :key="s.id"
          class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs hover:border-(--color-primary) hover:shadow-md transition flex flex-col justify-between"
        >
          <div>
            <div class="flex items-start justify-between mb-3">
              <div>
                <h4 class="text-sm font-bold text-slate-900 leading-snug">🔏 {{ s.name }}</h4>
                <span class="font-mono text-[11px] text-slate-400">{{ t('sealView.sealsTable.code') }}: {{ s.code }}</span>
              </div>
              <span class="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
                {{ t(`sealView.sealTypes.${s.seal_type}`, s.seal_type) }}
              </span>
            </div>

            <div class="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
              <div class="flex items-center justify-between">
                <span class="text-slate-500">{{ t('sealView.sealsTable.custodian') }}:</span>
                <span class="font-semibold text-slate-800">
                  {{ s.custodian_name ? `${s.custodian_name} (${s.custodian_employee_no || s.custodian_employee_id})` : s.custodian_employee_id }}
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-500">{{ t('sealView.sealsTable.effectivePeriod') }}:</span>
                <span class="font-mono text-[11px] text-slate-700">
                  {{ s.effective_from }} ~ {{ s.effective_to || t('sealView.sealsTable.permanent') }}
                </span>
              </div>

              <div class="flex items-center justify-between">
                <span class="text-slate-500">{{ t('sealView.sealsTable.status') }}:</span>
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-semibold"
                  :class="s.is_active ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600 border border-slate-200'"
                >
                  {{ s.is_active ? t('sealView.sealsTable.active') : t('usersView.table.suspended') }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 開立用印申請 Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">+ 提出用印申請</h3>
          <button @click="showCreateModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <FormField label="選擇用印印鑑" required>
            <select v-model="selectedSealId" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white">
              <option v-for="s in seals" :key="s.id" :value="s.id">
                {{ s.name }} ({{ s.code }}) - {{ s.seal_type }}
              </option>
            </select>
          </FormField>

          <FormField label="用印文件名稱" required>
            <input v-model="documentName" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="申請用印份數" required>
              <input v-model="copies" type="number" min="1" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="文件版本號">
              <input v-model="documentVersion" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <FormField label="用印具體用途與簽核事由" required>
            <textarea v-model="purpose" rows="3" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"></textarea>
          </FormField>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="saveSealRequest(false)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-sky-600 text-sky-700 hover:bg-sky-50 cursor-pointer"
          >
            儲存草稿
          </button>
          <button
            @click="saveSealRequest(true)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer"
          >
            {{ isSaving ? '處理中...' : '送出申請' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 執行實體用印 Modal -->
    <div v-if="showExecuteModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">🖋️ 印鑑保管人蓋印登記</h3>
          <button @click="showExecuteModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <FormField label="實際用印蓋章份數" required>
            <input v-model="sealedCopies" type="number" min="1" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
          <FormField label="用印後完簽掃描件歸檔網址">
            <input v-model="finalScanUrl" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showExecuteModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="doExecuteSeal"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs cursor-pointer"
          >
            {{ isSaving ? '登記中...' : '確認完成蓋印' }}
          </button>
        </div>
      </div>
    </div>
    <!-- 新增公司印鑑 Modal -->
    <div v-if="showCreateSealModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">🏛️ {{ t('sealView.createSealModal.title') }}</h3>
          <button @click="showCreateSealModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
          <div v-if="sealErrorMessage" class="p-3 text-xs bg-rose-50 text-rose-700 rounded-lg border border-rose-200">
            {{ sealErrorMessage }}
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('sealView.createSealModal.code')" required>
              <input
                v-model="newSealCode"
                type="text"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
                placeholder="例: SEAL-TW-CORP"
              />
            </FormField>

            <FormField :label="t('sealView.createSealModal.type')" required>
              <select
                v-model="newSealType"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-(--color-primary) bg-white"
              >
                <option v-for="opt in sealTypeOptions" :key="opt.value" :value="opt.value">
                  {{ t('sealView.sealTypes.' + opt.value) }}
                </option>
              </select>
            </FormField>
          </div>

          <FormField :label="t('sealView.createSealModal.name')" required>
            <input
              v-model="newSealName"
              type="text"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              placeholder="例: 宏津科技股份有限公司 業務合約專用章"
            />
          </FormField>

          <FormField :label="t('sealView.createSealModal.custodian')" required>
            <select
              v-model="newCustodianId"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-(--color-primary) bg-white"
            >
              <option value="" disabled>{{ t('sealView.createSealModal.selectCustodian') }}</option>
              <option v-for="emp in employees" :key="emp.id" :value="emp.id">
                {{ emp.full_name }} ({{ emp.employee_no }})
              </option>
            </select>
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('sealView.createSealModal.effectiveFrom')" required>
              <input
                v-model="newEffectiveFrom"
                type="date"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>

            <FormField :label="t('sealView.createSealModal.effectiveTo')">
              <input
                v-model="newEffectiveTo"
                type="date"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showCreateSealModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 cursor-pointer"
          >
            {{ t('sealView.createSealModal.cancel') }}
          </button>
          <button
            @click="saveNewSeal"
            :disabled="isSavingSeal"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer disabled:opacity-50"
          >
            {{ isSavingSeal ? '處理中...' : t('sealView.createSealModal.submit') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

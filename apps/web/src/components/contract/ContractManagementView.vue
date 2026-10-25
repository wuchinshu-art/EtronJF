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

interface ContractItem {
  id: string;
  contract_number: string;
  title: string;
  counterparty_name: string;
  contract_type: string;
  amount: number;
  amount_twd: number;
  currency: string;
  start_date: string;
  end_date: string | null;
  status: string;
  lifecycle_status: string;
}

const contracts = ref<ContractItem[]>([]);
const isLoading = ref(false);

// 開立合約審查 Modal
const showCreateModal = ref(false);
const counterpartyName = ref('');
const title = ref('');
const contractType = ref('PURCHASE');
const startDate = ref('');
const endDate = ref('');
const currency = ref('TWD');
const exchangeRate = ref('1.0000');
const amount = ref('120000');
const responsibleDept = ref('研發處');
const autoRenew = ref(false);
const needsSeal = ref(true);
const isSaving = ref(false);
const errorMessage = ref('');

// 歸檔 Modal
const showArchiveModal = ref(false);
const archivingContractId = ref('');
const signedDocUrl = ref('https://storage.etron.com/contracts/signed_countersigned.pdf');

async function fetchContracts() {
  isLoading.value = true;
  try {
    const res = await apiFetch(`/api/v1/contracts?company_id=${props.companyId}`);
    if (res.ok) {
      contracts.value = await res.json();
    }
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  counterpartyName.value = '東京先進半導體材料開發技術株式會社';
  title.value = '2026年度先進製程材料技術授權暨委任合約書';
  contractType.value = 'PURCHASE';
  const today = new Date().toISOString().split('T')[0];
  const nextYear = new Date();
  nextYear.setFullYear(nextYear.getFullYear() + 1);
  startDate.value = today;
  endDate.value = nextYear.toISOString().split('T')[0];
  currency.value = 'JPY';
  exchangeRate.value = '0.2150';
  amount.value = '5000000';
  responsibleDept.value = '研發處';
  autoRenew.value = true;
  needsSeal.value = true;
  errorMessage.value = '';
  showCreateModal.value = true;
}

async function saveContract(andSubmit: boolean = false) {
  if (!counterpartyName.value || !title.value || !startDate.value) {
    errorMessage.value = '請填寫相對人名稱、合約名稱與生效起始日';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const res = await apiFetch('/api/v1/contracts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: currentUser.value?.employee_id || 'EMP-DEFAULT',
        counterparty_name: counterpartyName.value,
        title: title.value,
        contract_type: contractType.value,
        start_date: startDate.value,
        end_date: endDate.value || null,
        currency: currency.value,
        exchange_rate: Number(exchangeRate.value),
        amount: Number(amount.value),
        responsible_department: responsibleDept.value,
        auto_renew: autoRenew.value,
        needs_seal: needsSeal.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '建立合約審查單失敗');
    }

    const created = await res.json();
    if (andSubmit && created.contract_id) {
      const submitRes = await apiFetch(`/api/v1/contracts/${created.contract_id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!submitRes.ok) {
        const err = await submitRes.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '合約建立成功，但送審失敗');
      }
    }

    showCreateModal.value = false;
    await fetchContracts();
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSaving.value = false;
  }
}

async function submitSingleContract(id: string) {
  try {
    const res = await apiFetch(`/api/v1/contracts/${id}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      await fetchContracts();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.error?.message || err.message || '送審失敗');
    }
  } catch {
    alert('送審連線錯誤');
  }
}

function openArchiveModal(id: string) {
  archivingContractId.value = id;
  showArchiveModal.value = true;
}

async function doArchive() {
  isSaving.value = true;
  try {
    const res = await apiFetch(`/api/v1/contracts/${archivingContractId.value}/archive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signed_document_url: signedDocUrl.value }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || '合約歸檔失敗');
    }

    showArchiveModal.value = false;
    await fetchContracts();
  } catch (err: any) {
    alert(err.message || '連線錯誤');
  } finally {
    isSaving.value = false;
  }
}

watch(() => props.companyId, () => fetchContracts());
onMounted(() => fetchContracts());
</script>

<template>
  <div class="space-y-6">
    <!-- 功能標題列 -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold text-slate-800">📜 {{ t('contractView.title') }}</h2>
        <p class="text-xs text-text-muted">{{ t('contractView.subtitle') }}</p>
      </div>
      <button
        @click="openCreateModal"
        class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
      >
        {{ t('contractView.createContract') }}
      </button>
    </div>

    <!-- 合約清單 -->
    <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <h3 class="text-xs font-semibold text-slate-700">📑 {{ t('contractView.listTitle') }}</h3>
        <button @click="fetchContracts" class="text-xs text-sky-600 hover:text-sky-800 font-medium cursor-pointer">
          {{ t('contractView.refresh') }}
        </button>
      </div>

      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="contracts.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('contractView.noContracts') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('contractView.table.contractNo') }}</th>
              <th class="px-4 py-3">{{ t('contractView.table.title') }}</th>
              <th class="px-4 py-3">{{ t('contractView.table.counterparty') }}</th>
              <th class="px-4 py-3">{{ t('contractView.table.type') }}</th>
              <th class="px-4 py-3 text-right">{{ t('contractView.table.amountTwd') }}</th>
              <th class="px-4 py-3">{{ t('contractView.table.validityPeriod') }}</th>
              <th class="px-4 py-3">{{ t('contractView.table.approvalStatus') }}</th>
              <th class="px-4 py-3">{{ t('contractView.table.lifecycleStatus') }}</th>
              <th class="px-4 py-3 text-right">{{ t('contractView.table.actions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="c in contracts" :key="c.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ c.contract_number }}</td>
              <td class="px-4 py-3 font-semibold text-slate-800">{{ c.title }}</td>
              <td class="px-4 py-3 text-slate-600">{{ c.counterparty_name }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-50 text-sky-700 border border-sky-200">
                  {{ c.contract_type }}
                </span>
              </td>
              <td class="px-4 py-3 text-right font-mono font-bold text-slate-900">
                NT$ {{ c.amount_twd.toLocaleString() }}
              </td>
              <td class="px-4 py-3 font-mono text-slate-600 text-[11px]">
                {{ c.start_date }} ~ {{ c.end_date || t('contractView.table.noLimit') }}
              </td>
              <td class="px-4 py-3">
                <StatusBadge :status="c.status" />
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-semibold"
                  :class="c.lifecycle_status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'"
                >
                  {{ c.lifecycle_status === 'ACTIVE' ? t('usersView.table.active') : c.lifecycle_status }}
                </span>
              </td>
              <td class="px-4 py-3 text-right space-x-2">
                <button
                  v-if="c.status === 'DRAFT'"
                  @click="submitSingleContract(c.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded transition cursor-pointer"
                >
                  {{ t('contractView.table.submit') }}
                </button>
                <button
                  v-if="c.status === 'APPROVED' && c.lifecycle_status !== 'ARCHIVED'"
                  @click="openArchiveModal(c.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded transition cursor-pointer"
                >
                  📁 歸檔
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 開立合約審查 Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">+ 開立合約審查單</h3>
          <button @click="showCreateModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <FormField label="簽約相對人法定名稱" required>
            <input v-model="counterpartyName" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>

          <FormField label="合約名稱 / 標題" required>
            <input v-model="title" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="合約類型">
              <select v-model="contractType" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="PURCHASE">採購合約 (Purchase)</option>
                <option value="SALES">銷售合約 (Sales)</option>
                <option value="NDA">保密協議 (NDA)</option>
                <option value="SERVICE">勞務委任 (Service)</option>
                <option value="LEASE">租賃合約 (Lease)</option>
              </select>
            </FormField>
            <FormField label="主辦責任部門">
              <input v-model="responsibleDept" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="grid grid-cols-3 gap-3">
            <FormField label="幣別">
              <select v-model="currency" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="TWD">TWD</option>
                <option value="JPY">JPY</option>
                <option value="USD">USD</option>
              </select>
            </FormField>
            <FormField label="匯率">
              <input v-model="exchangeRate" type="number" step="0.0001" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="合約總金額">
              <input v-model="amount" type="number" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="生效起始日" required>
              <input v-model="startDate" type="date" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="合約截止日 (可為空)">
              <input v-model="endDate" type="date" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="flex items-center space-x-6 pt-1">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="checkbox" v-model="needsSeal" class="rounded text-(--color-primary)" />
              <span class="text-xs font-semibold text-slate-800">完簽後需要實體用印 (Need Seal)</span>
            </label>
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="checkbox" v-model="autoRenew" class="rounded text-(--color-primary)" />
              <span class="text-xs font-semibold text-slate-800">屆期自動展延 (Auto Renew)</span>
            </label>
          </div>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="saveContract(false)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-sky-600 text-sky-700 hover:bg-sky-50 cursor-pointer"
          >
            儲存草稿
          </button>
          <button
            @click="saveContract(true)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer"
          >
            {{ isSaving ? '處理中...' : '送出申請' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 歸檔 Modal -->
    <div v-if="showArchiveModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">📁 合約簽署完畢歸檔</h3>
          <button @click="showArchiveModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <FormField label="雙方簽署後掃描件儲存路徑 / 網址" required>
            <input v-model="signedDocUrl" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showArchiveModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="doArchive"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer"
          >
            確認歸檔
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

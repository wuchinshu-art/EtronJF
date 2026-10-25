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

interface ExpenseClaimItem {
  id: string;
  claim_number: string;
  title: string;
  total_amount: number;
  total_amount_twd: number;
  currency: string;
  status: string;
  payment_status: string;
  has_duplicate_warning: boolean;
  created_at: string;
}

const claims = ref<ExpenseClaimItem[]>([]);
const isLoading = ref(false);
const showCreateModal = ref(false);
const isSaving = ref(false);
const errorMessage = ref('');

// 新建費用報銷表單
const formTitle = ref('');
const formCurrency = ref('TWD');
const formCostCenter = ref('RD-DEPT');
const formTaxAmount = ref('0');
const formNotes = ref('');

// 明細項目
const itemCategory = ref('MEAL');
const itemDate = ref('');
const itemInvoice = ref('');
const itemAmount = ref('2500');
const itemDesc = ref('');

async function fetchClaims() {
  isLoading.value = true;
  try {
    const res = await apiFetch(`/api/v1/expense/claims?company_id=${props.companyId}`);
    if (res.ok) {
      claims.value = await res.json();
    }
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  formTitle.value = '專案技術交流與業務拜訪費用報支';
  formCurrency.value = 'TWD';
  formCostCenter.value = 'RD-DEPT';
  formTaxAmount.value = '125';
  formNotes.value = '客戶洽談與相關餐費憑證報支';
  itemCategory.value = 'MEAL';
  itemDate.value = new Date().toISOString().split('T')[0];
  itemInvoice.value = 'INV-202610-888';
  itemAmount.value = '2500';
  itemDesc.value = '與專案合作夥伴商務餐敘';
  errorMessage.value = '';
  showCreateModal.value = true;
}

async function saveClaim(andSubmit: boolean = false) {
  if (!formTitle.value || !itemAmount.value || !itemDesc.value) {
    errorMessage.value = '請填寫報支標題與費用項目明細';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const res = await apiFetch('/api/v1/expense/claims', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: currentUser.value?.employee_id || 'EMP-DEFAULT',
        title: formTitle.value,
        currency: formCurrency.value,
        exchange_rate: 1.0,
        cost_center: formCostCenter.value,
        tax_amount: Number(formTaxAmount.value),
        notes: formNotes.value,
        items: [
          {
            category: itemCategory.value,
            expense_date: itemDate.value,
            invoice_number: itemInvoice.value || null,
            currency: formCurrency.value,
            exchange_rate: 1.0,
            amount: Number(itemAmount.value),
            description: itemDesc.value,
          },
        ],
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '開立費用報銷單失敗');
    }

    const created = await res.json();

    if (andSubmit && created.claim_id) {
      const submitRes = await apiFetch(`/api/v1/expense/claims/${created.claim_id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!submitRes.ok) {
        const err = await submitRes.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '報銷單建立成功，但送審失敗');
      }
    }

    showCreateModal.value = false;
    await fetchClaims();
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSaving.value = false;
  }
}

async function submitSingleClaim(id: string) {
  try {
    const res = await apiFetch(`/api/v1/expense/claims/${id}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      await fetchClaims();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.error?.message || err.message || '送審失敗');
    }
  } catch {
    alert('送審連線錯誤');
  }
}

watch(() => props.companyId, () => fetchClaims());
onMounted(() => fetchClaims());
</script>

<template>
  <div class="space-y-6">
    <!-- 功能標題列 -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold text-slate-800">📰 {{ t('expenseView.title') }}</h2>
        <p class="text-xs text-text-muted">{{ t('expenseView.subtitle') }}</p>
      </div>
      <button
        @click="openCreateModal"
        class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
      >
        {{ t('expenseView.createClaim') }}
      </button>
    </div>

    <!-- 費用報銷單列表 -->
    <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <h3 class="text-xs font-semibold text-slate-700">📑 {{ t('expenseView.listTitle') }}</h3>
        <button @click="fetchClaims" class="text-xs text-sky-600 hover:text-sky-800 font-medium cursor-pointer">
          {{ t('expenseView.refresh') }}
        </button>
      </div>

      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="claims.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('expenseView.noClaims') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('expenseView.table.claimNo') }}</th>
              <th class="px-4 py-3">{{ t('expenseView.table.subject') }}</th>
              <th class="px-4 py-3">{{ t('expenseView.table.currency') }}</th>
              <th class="px-4 py-3 text-right">{{ t('expenseView.table.amountTwd') }}</th>
              <th class="px-4 py-3">{{ t('expenseView.table.invoiceStatus') }}</th>
              <th class="px-4 py-3">{{ t('expenseView.table.approvalStatus') }}</th>
              <th class="px-4 py-3">{{ t('expenseView.table.paymentStatus') }}</th>
              <th class="px-4 py-3 text-right">{{ t('expenseView.table.actions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="c in claims" :key="c.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ c.claim_number }}</td>
              <td class="px-4 py-3 font-semibold text-slate-800">{{ c.title }}</td>
              <td class="px-4 py-3 font-mono text-slate-600">{{ c.currency }}</td>
              <td class="px-4 py-3 text-right font-mono font-bold text-slate-900">
                NT$ {{ c.total_amount_twd.toLocaleString() }}
              </td>
              <td class="px-4 py-3">
                <span
                  v-if="c.has_duplicate_warning"
                  class="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200"
                >
                  {{ t('expenseView.table.duplicateWarning') }}
                </span>
                <span v-else class="text-slate-400 text-[11px]">{{ t('expenseView.table.normalInvoice') }}</span>
              </td>
              <td class="px-4 py-3">
                <StatusBadge :status="c.status" />
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-semibold"
                  :class="c.payment_status === 'PAID' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'"
                >
                  {{ c.payment_status === 'PAID' ? t('expenseView.table.paid') : t('expenseView.table.unpaid') }}
                </span>
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  v-if="c.status === 'DRAFT'"
                  @click="submitSingleClaim(c.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded transition cursor-pointer"
                >
                  {{ t('expenseView.table.submit') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 開立費用報銷 Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">+ 填寫費用報銷單</h3>
          <button @click="showCreateModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <FormField label="報支主旨標題" required>
            <input
              v-model="formTitle"
              type="text"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            />
          </FormField>

          <div class="grid grid-cols-3 gap-3">
            <FormField label="幣別">
              <select v-model="formCurrency" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="TWD">TWD</option>
                <option value="JPY">JPY</option>
                <option value="USD">USD</option>
              </select>
            </FormField>
            <FormField label="成本中心">
              <input v-model="formCostCenter" type="text" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="營業稅額">
              <input v-model="formTaxAmount" type="number" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3">
            <h4 class="text-xs font-bold text-slate-700">單筆費用項目憑證資訊</h4>
            <div class="grid grid-cols-2 gap-3">
              <FormField label="類別">
                <select v-model="itemCategory" class="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300 bg-white">
                  <option value="MEAL">商務餐飲 (Meal)</option>
                  <option value="TRANSPORT">交通通訊 (Transport)</option>
                  <option value="OFFICE">辦公用品 (Office)</option>
                  <option value="OTHER">其他雜支 (Other)</option>
                </select>
              </FormField>
              <FormField label="消費日期">
                <input v-model="itemDate" type="date" class="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300" />
              </FormField>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <FormField label="發票 / 憑證號碼" hint="將自動檢驗重複憑證">
                <input v-model="itemInvoice" type="text" class="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300" />
              </FormField>
              <FormField label="未稅金額" required>
                <input v-model="itemAmount" type="number" class="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300" />
              </FormField>
            </div>
            <FormField label="費用詳細說明" required>
              <input v-model="itemDesc" type="text" placeholder="例如：拜訪供應商餐敘" class="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <FormField label="備註">
            <input v-model="formNotes" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
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
            @click="saveClaim(false)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-sky-600 text-sky-700 hover:bg-sky-50 cursor-pointer"
          >
            儲存草稿
          </button>
          <button
            @click="saveClaim(true)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer"
          >
            {{ isSaving ? '送審中...' : '送出審核' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

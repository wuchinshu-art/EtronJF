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

interface VendorItem {
  id: string;
  company_id: string;
  code: string;
  name: string;
  country: string;
  tax_id: string | null;
  account_number_masked: string;
  bank_name: string | null;
  is_active: boolean;
}

interface PaymentRequestItem {
  id: string;
  payment_number: string;
  title: string;
  vendor_id: string;
  amount: number;
  amount_twd: number;
  currency: string;
  due_date: string;
  status: string;
  payment_status: string;
}

const activeTab = ref<'requests' | 'vendors'>('requests');
const requests = ref<PaymentRequestItem[]>([]);
const vendors = ref<VendorItem[]>([]);
const isLoading = ref(false);

// 開立請款單 Modal
const showCreateModal = ref(false);
const selectedVendorId = ref('');
const formTitle = ref('');
const formCurrency = ref('TWD');
const formExchangeRate = ref('1.0000');
const formAmount = ref('35000');
const formDueDate = ref('');
const formPaymentMethod = ref('WIRE');
const formInvoiceNo = ref('');
const formInvoiceDate = ref('');
const formDesc = ref('');
const isSaving = ref(false);
const errorMessage = ref('');

// 新增供應商 Modal
const showVendorModal = ref(false);
const vendorCode = ref('');
const vendorName = ref('');
const vendorTaxId = ref('');
const vendorBankName = ref('台灣銀行 (Bank of Taiwan)');
const vendorAccountNo = ref('0041234567890');
const vendorTerms = ref('NET30');

async function fetchData() {
  isLoading.value = true;
  try {
    const [reqsRes, vendsRes] = await Promise.all([
      apiFetch(`/api/v1/payment/requests?company_id=${props.companyId}`),
      apiFetch(`/api/v1/vendors?company_id=${props.companyId}`),
    ]);

    if (reqsRes.ok) requests.value = await reqsRes.json();
    if (vendsRes.ok) vendors.value = await vendsRes.json();
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  selectedVendorId.value = vendors.value[0]?.id || '';
  formTitle.value = '第四季資訊設備維護與耗材採購請款';
  formCurrency.value = 'TWD';
  formExchangeRate.value = '1.0000';
  formAmount.value = '35000';
  const nextMonth = new Date();
  nextMonth.setDate(nextMonth.getDate() + 30);
  formDueDate.value = nextMonth.toISOString().split('T')[0];
  formPaymentMethod.value = 'WIRE';
  formInvoiceNo.value = 'INV-2026-9012';
  formInvoiceDate.value = new Date().toISOString().split('T')[0];
  formDesc.value = '採購維護月結請款作業';
  errorMessage.value = '';
  showCreateModal.value = true;
}

async function savePaymentRequest(andSubmit: boolean = false) {
  if (!selectedVendorId.value || !formTitle.value || !formAmount.value || !formDueDate.value) {
    errorMessage.value = '請填寫受款廠商、請款標題、金額與預計付款日';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const res = await apiFetch('/api/v1/payment/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: currentUser.value?.employee_id || 'EMP-DEFAULT',
        vendor_id: selectedVendorId.value,
        title: formTitle.value,
        currency: formCurrency.value,
        exchange_rate: Number(formExchangeRate.value),
        amount: Number(formAmount.value),
        due_date: formDueDate.value,
        payment_method: formPaymentMethod.value,
        invoice_number: formInvoiceNo.value || null,
        invoice_date: formInvoiceDate.value || null,
        description: formDesc.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || err.message || err.detail || '建立請款單失敗');
    }

    const created = await res.json();
    if (andSubmit && created.payment_id) {
      const submitRes = await apiFetch(`/api/v1/payment/requests/${created.payment_id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!submitRes.ok) {
        const err = await submitRes.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '請款單建立成功，但送審失敗');
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
    const res = await apiFetch(`/api/v1/payment/requests/${id}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
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

function openVendorModal() {
  vendorCode.value = `VEND-${Math.floor(100 + Math.random() * 900)}`;
  vendorName.value = '台灣精密光電供應科技股份有限公司';
  vendorTaxId.value = '88234567';
  vendorBankName.value = '台灣銀行 (004)';
  vendorAccountNo.value = '0041234567890';
  vendorTerms.value = 'NET30';
  showVendorModal.value = true;
}

async function saveVendor() {
  if (!vendorCode.value || !vendorName.value) {
    alert('請填寫供應商代碼與公司名稱');
    return;
  }
  isSaving.value = true;
  try {
    const res = await apiFetch('/api/v1/vendors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        code: vendorCode.value,
        name: vendorName.value,
        tax_id: vendorTaxId.value || null,
        bank_name: vendorBankName.value,
        account_number: vendorAccountNo.value,
        payment_terms: vendorTerms.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || '建立供應商失敗');
    }

    showVendorModal.value = false;
    activeTab.value = 'vendors';
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
        <h2 class="text-base font-bold text-slate-800">💵 {{ t('paymentView.title') }}</h2>
        <p class="text-xs text-text-muted">{{ t('paymentView.subtitle') }}</p>
      </div>
      <div class="flex items-center space-x-2">
        <button
          @click="openVendorModal"
          class="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 shadow-xs transition cursor-pointer"
        >
          {{ t('paymentView.registerVendor') }}
        </button>
        <button
          @click="openCreateModal"
          class="px-3.5 py-1.5 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
        >
          {{ t('paymentView.createPayment') }}
        </button>
      </div>
    </div>

    <!-- 頁籤導航 -->
    <div class="flex space-x-2 border-b border-border-main">
      <button
        @click="activeTab = 'requests'"
        class="px-4 py-2 text-xs font-semibold border-b-2 transition cursor-pointer"
        :class="activeTab === 'requests' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
      >
        📑 {{ t('paymentView.tabs.payments') }} ({{ requests.length }})
      </button>
      <button
        @click="activeTab = 'vendors'"
        class="px-4 py-2 text-xs font-semibold border-b-2 transition cursor-pointer"
        :class="activeTab === 'vendors' ? 'border-(--color-primary) text-(--color-primary)' : 'border-transparent text-slate-500 hover:text-slate-700'"
      >
        🏢 {{ t('paymentView.tabs.vendors') }} ({{ vendors.length }})
      </button>
    </div>

    <!-- 請款單清單 -->
    <div v-if="activeTab === 'requests'" class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="requests.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('paymentView.noPayments') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('paymentView.paymentsTable.paymentNo') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.paymentsTable.subject') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.paymentsTable.vendorSnapshot') }}</th>
              <th class="px-4 py-3 text-right">{{ t('paymentView.paymentsTable.amount') }}</th>
              <th class="px-4 py-3 text-right">{{ t('expenseView.table.amountTwd') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.paymentsTable.expectedDate') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.paymentsTable.approvalStatus') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.paymentsTable.paymentStatus') }}</th>
              <th class="px-4 py-3 text-right">{{ t('paymentView.paymentsTable.actions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="r in requests" :key="r.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ r.payment_number }}</td>
              <td class="px-4 py-3 font-semibold text-slate-800">{{ r.title }}</td>
              <td class="px-4 py-3 font-mono text-slate-600 text-[11px]">{{ r.vendor_id.substring(0, 10) }}...</td>
              <td class="px-4 py-3 text-right font-mono text-slate-800">{{ r.currency }} {{ r.amount.toLocaleString() }}</td>
              <td class="px-4 py-3 text-right font-mono font-bold text-slate-900">
                NT$ {{ r.amount_twd.toLocaleString() }}
              </td>
              <td class="px-4 py-3 font-mono text-slate-600 text-[11px]">{{ r.due_date }}</td>
              <td class="px-4 py-3">
                <StatusBadge :status="r.status" />
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-semibold"
                  :class="r.payment_status === 'PAID' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600'"
                >
                  {{ r.payment_status === 'PAID' ? t('paymentView.paymentsTable.paid') : t('paymentView.paymentsTable.unpaid') }}
                </span>
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  v-if="r.status === 'DRAFT'"
                  @click="submitSingleRequest(r.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded transition cursor-pointer"
                >
                  {{ t('paymentView.paymentsTable.submit') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 供應商名冊清單 -->
    <div v-else class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="vendors.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('paymentView.noVendors') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('paymentView.vendorsTable.code') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.vendorsTable.name') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.vendorsTable.taxId') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.vendorsTable.bank') }}</th>
              <th class="px-4 py-3">{{ t('paymentView.vendorsTable.accountMasked') }}</th>
              <th class="px-4 py-3">{{ t('sealView.sealsTable.status') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="v in vendors" :key="v.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ v.code }}</td>
              <td class="px-4 py-3 font-semibold text-slate-800">{{ v.name }}</td>
              <td class="px-4 py-3 font-mono text-slate-600">{{ v.tax_id || '—' }}</td>
              <td class="px-4 py-3 text-slate-600">{{ v.bank_name || '—' }}</td>
              <td class="px-4 py-3 font-mono font-semibold text-slate-700">{{ v.account_number_masked }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  {{ v.is_active ? t('sealView.sealsTable.active') : t('usersView.table.suspended') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 開立請款單 Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">+ 開立廠商請款單</h3>
          <button @click="showCreateModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <FormField label="受款供應商" required hint="單據送簽時將保存不可變快照">
            <select v-model="selectedVendorId" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white">
              <option v-for="v in vendors" :key="v.id" :value="v.id">
                {{ v.name }} ({{ v.code }}) - {{ v.bank_name }}
              </option>
            </select>
          </FormField>

          <FormField label="請款單主旨" required>
            <input v-model="formTitle" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>

          <div class="grid grid-cols-3 gap-3">
            <FormField label="請款幣別">
              <select v-model="formCurrency" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="TWD">TWD</option>
                <option value="JPY">JPY</option>
                <option value="USD">USD</option>
              </select>
            </FormField>
            <FormField label="折合匯率">
              <input v-model="formExchangeRate" type="number" step="0.0001" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="請款金額" required>
              <input v-model="formAmount" type="number" class="w-full px-2 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="預計付款日期" required>
              <input v-model="formDueDate" type="date" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="付款方式">
              <select v-model="formPaymentMethod" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white">
                <option value="WIRE">銀行電匯 (Wire Transfer)</option>
                <option value="CHECK">劃線支票 (Check)</option>
              </select>
            </FormField>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <FormField label="發票號碼">
              <input v-model="formInvoiceNo" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
            <FormField label="發票開立日期">
              <input v-model="formInvoiceDate" type="date" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
            </FormField>
          </div>

          <FormField label="備註說明">
            <textarea v-model="formDesc" rows="2" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"></textarea>
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
            @click="savePaymentRequest(false)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-sky-600 text-sky-700 hover:bg-sky-50 cursor-pointer"
          >
            儲存草稿
          </button>
          <button
            @click="savePaymentRequest(true)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer"
          >
            {{ isSaving ? '處理中...' : '送出申請' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 註冊供應商 Modal -->
    <div v-if="showVendorModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">+ 註冊供應商主檔</h3>
          <button @click="showVendorModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <FormField label="供應商代碼" required>
            <input v-model="vendorCode" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
          <FormField label="供應商法定名稱" required>
            <input v-model="vendorName" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
          <FormField label="統一編號 / 法人號碼">
            <input v-model="vendorTaxId" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
          <FormField label="受款往來銀行">
            <input v-model="vendorBankName" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
          <FormField label="受款銀行帳號" hint="儲存後將受隱私權限保護並遮罩">
            <input v-model="vendorAccountNo" type="text" class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300" />
          </FormField>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showVendorModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="saveVendor"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer"
          >
            確認註冊
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

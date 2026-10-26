<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import { useTranslation } from 'i18next-vue';
import StatusBadge from '../common/StatusBadge.vue';
import { apiFetch, currentUser } from '../../utils/auth';

const props = defineProps<{
  companyId: string;
  timezone: string;
}>();

const { t } = useTranslation();

interface LeaveRequestItem {
  id: string;
  company_id: string;
  employee_id: string;
  leave_type_id: string;
  request_number: string;
  start_time: string;
  end_time: string;
  total_minutes: number;
  calculated_days: number;
  reason: string;
  deputy_employee_id: string | null;
  status: string;
  created_at: string;
}

interface LeaveTypeItem {
  id: string;
  code: string;
  name: string;
  unit: string;
}

interface EmployeeItem {
  id: string;
  employee_no: string;
  full_name: string;
  organization_id?: string;
  organization_name?: string;
  department_name?: string;
}

const leaveRequests = ref<LeaveRequestItem[]>([]);
const leaveTypes = ref<LeaveTypeItem[]>([]);
const employees = ref<EmployeeItem[]>([]);
const isLoading = ref(false);
const showCreateModal = ref(false);
const isSaving = ref(false);
const isCalculating = ref(false);
const errorMessage = ref('');

// 新建表單欄位
const selectedEmployeeId = ref('');
const applicantDisplayName = ref('');
const applicantDeptName = ref('');
const applicantManagerName = ref('');
const requestNumberPreview = ref('');
const applicationDate = ref('');

// 經典表單請假類型選項清單 (符合企業人資規範)
const standardLeaveTypes = [
  { key: 'ANNUAL', label: '特休假' },
  { key: 'COMPENSATORY', label: '補休假' },
  { key: 'OFFICIAL', label: '公假' },
  { key: 'PERSONAL', label: '事假' },
  { key: 'SICK', label: '病假' },
  { key: 'FUNERAL', label: '喪假' },
  { key: 'MARRIAGE', label: '婚假' },
  { key: 'MATERNITY', label: '產假' },
  { key: 'PATERNITY', label: '陪產假' },
  { key: 'MENSTRUAL', label: '生理假' },
  { key: 'OTHER', label: '其他' },
] as const;

const selectedLeaveTypeKey = ref<string>('ANNUAL');
const otherLeaveText = ref('');
const startTime = ref('');
const endTime = ref('');
const reason = ref('');
const remarks = ref('');
const deputyEmployeeId = ref('');
const calculatedInfo = ref<{ minutes: number; days: number } | null>(null);

// 計算總時數 (小時)
const calculatedHours = computed(() => {
  if (!calculatedInfo.value) return 0;
  return Number((calculatedInfo.value.minutes / 60).toFixed(1));
});

async function fetchData() {
  isLoading.value = true;
  try {
    const [reqsRes, typesRes, empsRes] = await Promise.all([
      apiFetch(`/api/v1/leave/requests?company_id=${props.companyId}`),
      apiFetch('/api/v1/hr/leave-types'),
      apiFetch(`/api/v1/hr/employees?company_id=${props.companyId}`),
    ]);

    if (reqsRes.ok) leaveRequests.value = await reqsRes.json();
    if (typesRes.ok) leaveTypes.value = await typesRes.json();
    if (empsRes.ok) {
      const empsData = await empsRes.json();
      employees.value = Array.isArray(empsData) ? empsData : (empsData.items || []);
    }
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

// 根據所選員工自動動態查詢並帶出部門與主管資訊
async function onEmployeeChanged() {
  if (!selectedEmployeeId.value) return;

  const targetEmp = employees.value.find(e => e.id === selectedEmployeeId.value);
  if (targetEmp) {
    applicantDisplayName.value = `${targetEmp.full_name} (${targetEmp.employee_no})`;
  }

  try {
    const res = await apiFetch(`/api/v1/hr/employees/${selectedEmployeeId.value}`);
    if (res.ok) {
      const detail = await res.json();
      applicantDeptName.value = detail.department_name || detail.organization_name || '未指定部門';
      if (detail.manager && detail.manager.manager_name) {
        applicantManagerName.value = `${detail.manager.manager_name} (${detail.manager.manager_no})`;
      } else {
        applicantManagerName.value = '無 (由人資窗口/直屬代理簽核)';
      }
    }
  } catch {
    // 降級保護
    if (currentUser.value && currentUser.value.employee_id === selectedEmployeeId.value) {
      applicantDeptName.value = currentUser.value.department_name || '未指定部門';
      applicantManagerName.value = currentUser.value.manager_name ? `${currentUser.value.manager_name} (${currentUser.value.manager_no || ''})` : '無 (待指派主管)';
    }
  }

  await calculateLeaveTime();
}

function openCreateModal() {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const todayStr = `${yyyy}-${mm}-${dd}`;

  applicationDate.value = `${yyyy}/${mm}/${dd}`;
  requestNumberPreview.value = `LV-${yyyy}${mm}${dd}-XXXX (送出後核發)`;

  // 1. 申請人：自動依登入帳號帶出
  if (currentUser.value?.employee_id) {
    selectedEmployeeId.value = currentUser.value.employee_id;
    applicantDisplayName.value = `${currentUser.value.display_name} (${currentUser.value.employee_no || currentUser.value.username})`;
  } else if (employees.value.length > 0) {
    selectedEmployeeId.value = employees.value[0].id;
    applicantDisplayName.value = `${employees.value[0].full_name} (${employees.value[0].employee_no})`;
  } else {
    selectedEmployeeId.value = '';
    applicantDisplayName.value = currentUser.value?.display_name || '未登入';
  }

  // 2. 申請部門：先以登入帳號帶出
  applicantDeptName.value = currentUser.value?.department_name || '正在載入部門...';

  // 3. 主管：先以登入帳號帶出
  if (currentUser.value?.manager_name) {
    applicantManagerName.value = `${currentUser.value.manager_name} (${currentUser.value.manager_no || ''})`;
  } else {
    applicantManagerName.value = '正在查詢直屬主管...';
  }

  // 表單欄位初始化
  selectedLeaveTypeKey.value = 'ANNUAL';
  otherLeaveText.value = '';
  startTime.value = `${todayStr}T09:00`;
  endTime.value = `${todayStr}T18:00`;
  reason.value = '';
  remarks.value = '';
  deputyEmployeeId.value = '';
  calculatedInfo.value = null;
  errorMessage.value = '';
  showCreateModal.value = true;

  // 立即非同步校驗最新部門與主管資訊
  if (selectedEmployeeId.value) {
    onEmployeeChanged();
  } else {
    calculateLeaveTime();
  }
}

async function calculateLeaveTime() {
  if (!startTime.value || !endTime.value || !selectedEmployeeId.value) return;
  isCalculating.value = true;
  try {
    const res = await apiFetch('/api/v1/leave/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        employee_id: selectedEmployeeId.value,
        start_time: new Date(startTime.value).toISOString(),
        end_time: new Date(endTime.value).toISOString(),
      }),
    });
    if (res.ok) {
      const data = await res.json();
      calculatedInfo.value = {
        minutes: data.total_minutes,
        days: data.calculated_days,
      };
    }
  } catch {
    // 試算錯誤靜默
  } finally {
    isCalculating.value = false;
  }
}

async function submitLeave(andSubmit: boolean = false) {
  if (!selectedEmployeeId.value) {
    errorMessage.value = '找不到申請員工識別碼，請確認登入身分或聯絡管理員';
    return;
  }

  if (!deputyEmployeeId.value) {
    errorMessage.value = '請選擇工作代理人 (Deputy is required)';
    return;
  }

  if (!startTime.value || !endTime.value || !reason.value.trim()) {
    errorMessage.value = '請完整填寫請假起訖時間與請假事由';
    return;
  }

  if (selectedLeaveTypeKey.value === 'OTHER' && !otherLeaveText.value.trim()) {
    errorMessage.value = '您選擇了「其他」假別，請填寫具體假別說明';
    return;
  }

  errorMessage.value = '';
  isSaving.value = true;

  try {
    // 解析對應假別 ID：優先在公司假別清單比對 code，若無則傳送選項 key 由後端智能補齊
    const matched = leaveTypes.value.find(
      lt => lt.code.toUpperCase() === selectedLeaveTypeKey.value || lt.id.toUpperCase() === selectedLeaveTypeKey.value
    );
    const resolvedLeaveTypeId = matched ? matched.id : selectedLeaveTypeKey.value;

    // 整合事由與備註
    let fullReason = reason.value.trim();
    if (selectedLeaveTypeKey.value === 'OTHER' && otherLeaveText.value.trim()) {
      fullReason = `【其他假別: ${otherLeaveText.value.trim()}】 ${fullReason}`;
    }
    if (remarks.value.trim()) {
      fullReason += `\n(備註: ${remarks.value.trim()})`;
    }

    const res = await apiFetch('/api/v1/leave/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: selectedEmployeeId.value,
        leave_type_id: resolvedLeaveTypeId,
        start_time: new Date(startTime.value).toISOString(),
        end_time: new Date(endTime.value).toISOString(),
        reason: fullReason,
        deputy_employee_id: deputyEmployeeId.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || err.detail || '請假申請失敗');
    }

    const created = await res.json();

    if (andSubmit && created.id) {
      await apiFetch(`/api/v1/leave/requests/${created.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
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
    const res = await apiFetch(`/api/v1/leave/requests/${id}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      await fetchData();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.message || '送審失敗');
    }
  } catch {
    alert('送審連線錯誤');
  }
}

async function cancelSingleRequest(id: string) {
  if (!confirm('確定要抽單／撤回此請假申請嗎？')) return;
  try {
    const res = await apiFetch(`/api/v1/leave/requests/${id}/cancel`, {
      method: 'POST',
    });
    if (res.ok) {
      await fetchData();
    } else {
      const err = await res.json().catch(() => ({}));
      alert(err.message || '撤回失敗');
    }
  } catch {
    alert('撤回連線錯誤');
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
        <h2 class="text-base font-bold text-slate-800">🌴 請假管理 (Leave Management)</h2>
        <p class="text-xs text-text-muted">支援排班工時精準試算、自動扣除休息時間、假額預占與多級簽核管理</p>
      </div>
      <button
        @click="openCreateModal"
        class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
      >
        + 填寫請假申請單
      </button>
    </div>

    <!-- 請假單列表 -->
    <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <h3 class="text-xs font-semibold text-slate-700">📑 我的請假單清單</h3>
        <button @click="fetchData" class="text-xs text-sky-600 hover:text-sky-800 font-medium cursor-pointer">
          重新整理
        </button>
      </div>

      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="leaveRequests.length === 0" class="p-8 text-center text-xs text-text-muted">
        目前無請假申請紀錄，點選上方按鈕開立請假單
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">請假單號</th>
              <th class="px-4 py-3">假別代碼</th>
              <th class="px-4 py-3">起訖時段 (本地)</th>
              <th class="px-4 py-3">折算天數 / 分鐘</th>
              <th class="px-4 py-3">事由說明</th>
              <th class="px-4 py-3">簽核狀態</th>
              <th class="px-4 py-3 text-right">動作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="r in leaveRequests" :key="r.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ r.request_number }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded bg-sky-50 text-sky-700 font-semibold border border-sky-200">
                  {{ r.leave_type_id }}
                </span>
              </td>
              <td class="px-4 py-3 text-slate-600 font-mono text-[11px]">
                {{ r.start_time.replace('T', ' ').substring(0, 16) }} ~ {{ r.end_time.replace('T', ' ').substring(0, 16) }}
              </td>
              <td class="px-4 py-3 font-semibold text-slate-800">
                {{ r.calculated_days }} 天 ({{ r.total_minutes }}分)
              </td>
              <td class="px-4 py-3 text-slate-600 max-w-50 truncate" :title="r.reason">{{ r.reason }}</td>
              <td class="px-4 py-3">
                <StatusBadge :status="r.status" />
              </td>
              <td class="px-4 py-3 text-right space-x-2">
                <button
                  v-if="r.status === 'DRAFT'"
                  @click="submitSingleRequest(r.id)"
                  class="px-2.5 py-1 text-[11px] font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded transition cursor-pointer"
                >
                  送審
                </button>
                <button
                  v-if="r.status === 'IN_REVIEW' || r.status === 'DRAFT'"
                  @click="cancelSingleRequest(r.id)"
                  class="px-2.5 py-1 text-[11px] font-medium text-rose-600 hover:text-rose-800 hover:bg-rose-50 rounded border border-rose-200 transition cursor-pointer"
                >
                  撤回
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 請假申請單 Modal (依標準表單格式精確設計) -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-3xl border border-slate-200 overflow-hidden animate-fade-in flex flex-col max-h-[92vh]">
        <!-- 彈窗頂端標題 -->
        <div class="px-6 py-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div class="flex items-center space-x-2">
            <span class="text-base">📝</span>
            <h3 class="text-base font-bold text-slate-800">請假申請表單</h3>
          </div>
          <button @click="showCreateModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer leading-none">&times;</button>
        </div>

        <div class="p-6 overflow-y-auto space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <!-- 右上角單號與日期區 -->
          <div class="flex justify-end text-xs text-slate-600 pb-1 font-mono">
            <div class="space-y-1 text-right">
              <p>申請單號：<span class="text-sky-700 font-semibold">{{ requestNumberPreview }}</span></p>
              <p>申請日期：<span class="text-slate-800 font-semibold">{{ applicationDate }}</span></p>
            </div>
          </div>

          <!-- 核心表性格局 (格狀邊框佈局，嚴格契合使用者規格) -->
          <div class="border border-slate-300 rounded-lg overflow-hidden bg-white shadow-2xs">
            <table class="w-full border-collapse text-xs">
              <tbody>
                <!-- 1. 申請人 與 申請部門 -->
                <tr class="border-b border-slate-300">
                  <th class="w-24 sm:w-28 bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    申請人
                  </th>
                  <td class="w-[35%] sm:w-[38%] p-3 border-r border-slate-300 bg-slate-50/50">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-slate-800 text-xs">{{ applicantDisplayName }}</span>
                      <span class="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded whitespace-nowrap">
                        🔒 帳號自動帶出
                      </span>
                    </div>
                  </td>
                  <th class="w-24 sm:w-28 bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    申請部門
                  </th>
                  <td class="p-3 bg-slate-50/50">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-slate-800 text-xs">{{ applicantDeptName }}</span>
                      <span class="text-[10px] text-sky-700 bg-sky-50 border border-sky-200 px-1.5 py-0.2 rounded whitespace-nowrap">
                        🔒 自動帶出
                      </span>
                    </div>
                  </td>
                </tr>

                <!-- 2. 代理人 與 主管 -->
                <tr class="border-b border-slate-300">
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    代理人 <span class="text-rose-500 font-bold">*</span>
                  </th>
                  <td class="p-2.5 border-r border-slate-300">
                    <select
                      v-model="deputyEmployeeId"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                    >
                      <option value="">-- 請選擇工作代理人 --</option>
                      <option
                        v-for="emp in employees.filter(e => e.id !== selectedEmployeeId)"
                        :key="emp.id"
                        :value="emp.id"
                      >
                        {{ emp.full_name }} ({{ emp.employee_no }})
                      </option>
                    </select>
                  </td>
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    主管
                  </th>
                  <td class="p-3 bg-slate-50/50">
                    <div class="flex items-center justify-between">
                      <span class="font-bold text-slate-800 text-xs">{{ applicantManagerName }}</span>
                      <span class="text-[10px] text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.2 rounded whitespace-nowrap">
                        🔒 自動關聯
                      </span>
                    </div>
                  </td>
                </tr>

                <!-- 3. 請假事由 -->
                <tr class="border-b border-slate-300">
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    請假事由 <span class="text-rose-500 font-bold">*</span>
                  </th>
                  <td colspan="3" class="p-2.5">
                    <input
                      v-model="reason"
                      type="text"
                      placeholder="請輸入請假詳細事由..."
                      class="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                    />
                  </td>
                </tr>

                <!-- 4. 請假類型 (單選選項方塊) -->
                <tr class="border-b border-slate-300">
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300 align-top">
                    請假類型 <span class="text-rose-500 font-bold">*</span>
                  </th>
                  <td colspan="3" class="p-3">
                    <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2.5">
                      <label
                        v-for="item in standardLeaveTypes"
                        :key="item.key"
                        class="inline-flex items-center space-x-1.5 cursor-pointer py-1 px-2 rounded hover:bg-slate-100 transition"
                      >
                        <input
                          type="radio"
                          name="leaveTypeRadios"
                          :value="item.key"
                          v-model="selectedLeaveTypeKey"
                          class="w-3.5 h-3.5 text-(--color-primary) focus:ring-(--color-primary)"
                        />
                        <span
                          class="text-xs"
                          :class="selectedLeaveTypeKey === item.key ? 'font-bold text-(--color-primary)' : 'text-slate-700'"
                        >
                          {{ item.label }}
                        </span>
                      </label>
                    </div>

                    <!-- 若選「其他」，展開額外說明輸入框 -->
                    <div v-if="selectedLeaveTypeKey === 'OTHER'" class="mt-2.5 pt-2.5 border-t border-slate-200 flex items-center space-x-2">
                      <span class="text-xs text-slate-600 font-medium">其他假別說明:</span>
                      <input
                        v-model="otherLeaveText"
                        type="text"
                        placeholder="例如：防疫照顧假、公傷病假..."
                        class="px-2.5 py-1 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) flex-1 max-w-sm"
                      />
                    </div>
                  </td>
                </tr>

                <!-- 5. 開始日期 與 結束日期 -->
                <tr class="border-b border-slate-300">
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    開始日期 <span class="text-rose-500 font-bold">*</span>
                  </th>
                  <td class="p-2.5 border-r border-slate-300">
                    <input
                      v-model="startTime"
                      type="datetime-local"
                      @change="calculateLeaveTime"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                    />
                  </td>
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    結束日期 <span class="text-rose-500 font-bold">*</span>
                  </th>
                  <td class="p-2.5">
                    <input
                      v-model="endTime"
                      type="datetime-local"
                      @change="calculateLeaveTime"
                      class="w-full px-2.5 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                    />
                  </td>
                </tr>

                <!-- 6. 請假時數 (即時工時試算) -->
                <tr class="border-b border-slate-300">
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300">
                    請假時數 <span class="text-rose-500 font-bold">*</span>
                  </th>
                  <td colspan="3" class="p-3 bg-sky-50/30">
                    <div class="flex items-center space-x-2">
                      <span v-if="isCalculating" class="text-xs text-sky-600">正在依班別日曆試算中...</span>
                      <div v-else-if="calculatedInfo" class="flex items-center space-x-2">
                        <span class="font-bold font-mono text-slate-900 text-sm">
                          {{ calculatedHours }} 小時
                        </span>
                        <span class="text-xs text-slate-500 font-mono">
                          (折算 {{ calculatedInfo.days }} 天 / {{ calculatedInfo.minutes }} 分鐘)
                        </span>
                        <span class="text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                          ✓ 已自動扣除非工作日與午休時間
                        </span>
                      </div>
                      <span v-else class="text-xs text-slate-400">請設定開始與結束時間以自動試算時數</span>
                    </div>
                  </td>
                </tr>

                <!-- 7. 備註 -->
                <tr>
                  <th class="bg-slate-100/80 p-3 font-semibold text-slate-700 text-left border-r border-slate-300 align-top">
                    備註
                  </th>
                  <td colspan="3" class="p-2.5">
                    <textarea
                      v-model="remarks"
                      rows="2"
                      placeholder="請填寫任何備註說明、交接事項或檢附證明說明..."
                      class="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
                    ></textarea>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 彈窗底部操作按鈕 -->
        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-end space-x-3">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 cursor-pointer"
          >
            取消
          </button>
          <button
            @click="submitLeave(false)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg border border-sky-600 text-sky-700 bg-sky-50/50 hover:bg-sky-100/50 cursor-pointer disabled:opacity-50"
          >
            儲存草稿
          </button>
          <button
            @click="submitLeave(true)"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer disabled:opacity-50"
          >
            {{ isSaving ? '送審中...' : '送出審核' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

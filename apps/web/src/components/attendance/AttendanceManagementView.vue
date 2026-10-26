<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { apiFetch, currentUser } from '../../utils/auth';
import { formatInTimezone } from '../../utils/time';

const props = defineProps<{
  companyId: string;
  timezone: string;
}>();

const { t } = useTranslation();

interface AttendanceEventItem {
  id: string;
  company_id: string;
  employee_id: string;
  event_at: string;
  raw_event_at_str: string;
  source_timezone: string;
  event_type: string;
  device_id: string | null;
  work_date: string;
  is_abnormal: boolean;
  abnormal_reason: string | null;
}

const events = ref<AttendanceEventItem[]>([]);
const isLoading = ref(false);
const isPunching = ref(false);
const punchMessage = ref('');
const currentTimeStr = ref('');
let timerId: any = null;

function updateClock() {
  const now = new Date();
  currentTimeStr.value = now.toLocaleTimeString('zh-TW', {
    timeZone: props.timezone,
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

async function fetchEvents() {
  isLoading.value = true;
  try {
    const res = await apiFetch(`/api/v1/attendance/events?company_id=${props.companyId}&limit=30`);
    if (res.ok) {
      const data = await res.json();
      events.value = data.items || [];
    }
  } catch {
    // 網路錯誤靜默
  } finally {
    isLoading.value = false;
  }
}

async function handlePunch(eventType: 'CHECK_IN' | 'CHECK_OUT') {
  isPunching.value = true;
  punchMessage.value = '';
  try {
    const res = await apiFetch('/api/v1/attendance/punch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        employee_id: currentUser.value?.employee_id || null,
        event_type: eventType,
        source_timezone: props.timezone,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || '打卡失敗');
    }

    const data = await res.json();
    punchMessage.value = `${eventType === 'CHECK_IN' ? '☀️ 上班' : '🌙 下班'}打卡成功！時間：${data.local_time_str}`;
    await fetchEvents();
  } catch (err: any) {
    punchMessage.value = `❌ ${err.message || '連線錯誤'}`;
  } finally {
    isPunching.value = false;
  }
}

// 快速 CSV 匯入區塊
const showImportModal = ref(false);
const importCsvText = ref(`employee_no,event_at,event_type
TW1001,2026-10-23 09:00:00,CHECK_IN
TW1001,2026-10-23 18:05:00,CHECK_OUT`);
const isImporting = ref(false);
const importMessage = ref('');

async function doImport() {
  isImporting.value = true;
  importMessage.value = '';
  try {
    const res = await apiFetch('/api/v1/attendance/imports/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company_id: props.companyId,
        file_name: 'portal_import.csv',
        file_text: importCsvText.value,
        file_format: 'CSV',
        encoding: 'UTF-8',
        source_timezone: props.timezone,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || '匯入失敗');
    }

    const batch = await res.json();
    // 自動執行 preview 與 commit
    const prevRes = await apiFetch(`/api/v1/attendance/imports/${batch.batch_id}/preview`, { method: 'POST' });
    const prevData = await prevRes.json();
    await apiFetch(`/api/v1/attendance/imports/${batch.batch_id}/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preview_revision: prevData.preview_revision }),
    });

    importMessage.value = `✅ 成功匯入並入庫 ${batch.total_rows} 筆打卡資料！`;
    showImportModal.value = false;
    await fetchEvents();
  } catch (err: any) {
    importMessage.value = `❌ ${err.message || '匯入發生錯誤'}`;
  } finally {
    isImporting.value = false;
  }
}

watch(() => props.timezone, () => updateClock());
watch(() => props.companyId, () => fetchEvents());

onMounted(() => {
  updateClock();
  timerId = setInterval(updateClock, 1000);
  fetchEvents();
});

onUnmounted(() => {
  if (timerId) clearInterval(timerId);
});
</script>

<template>
  <div class="space-y-6">
    <!-- 功能標題列 -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold text-slate-800">⏱️ {{ t('attendanceView.title') }}</h2>
        <p class="text-xs text-text-muted">{{ t('attendanceView.subtitle') }}</p>
      </div>
      <button
        @click="showImportModal = true"
        class="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 shadow-xs transition cursor-pointer"
      >
        📤 {{ t('attendanceView.batchImport') }}
      </button>
    </div>

    <!-- 在線打卡卡片 -->
    <div class="bg-linear-to-r from-sky-50 to-indigo-50 p-6 rounded-2xl border border-sky-100 flex flex-col md:flex-row items-center justify-between gap-6 shadow-xs">
      <div>
        <div class="flex items-center space-x-2 mb-1">
          <span class="text-xs font-semibold px-2 py-0.5 rounded bg-sky-100 text-sky-800">
            {{ t('attendanceView.currentCompany', { company: companyId }) }}
          </span>
          <span class="text-xs font-medium text-slate-500">
            {{ t('attendanceView.timezoneLabel', { tz: timezone === 'Asia/Tokyo' ? t('dashboard.tzTokyo') : t('dashboard.tzTaipei') }) }}
          </span>
        </div>
        <div class="text-3xl font-extrabold font-mono text-slate-800 tracking-wider">
          {{ currentTimeStr || '00:00:00' }}
        </div>
        <p v-if="punchMessage" class="mt-2 text-xs font-semibold" :class="punchMessage.startsWith('❌') ? 'text-rose-600' : 'text-emerald-600'">
          {{ punchMessage }}
        </p>
      </div>

      <!-- 打卡按鈕群 -->
      <div class="flex items-center space-x-4">
        <button
          @click="handlePunch('CHECK_IN')"
          :disabled="isPunching"
          class="px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm shadow-md hover:shadow-lg transition cursor-pointer disabled:opacity-50 flex items-center space-x-2"
        >
          <span>☀️</span>
          <span>{{ t('attendanceView.checkIn') }}</span>
        </button>
        <button
          @click="handlePunch('CHECK_OUT')"
          :disabled="isPunching"
          class="px-6 py-3 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-bold text-sm shadow-md hover:shadow-lg transition cursor-pointer disabled:opacity-50 flex items-center space-x-2"
        >
          <span>🌙</span>
          <span>{{ t('attendanceView.checkOut') }}</span>
        </button>
      </div>
    </div>

    <!-- 出勤打卡事件清單 -->
    <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <h3 class="text-xs font-semibold text-slate-700">📋 {{ t('attendanceView.eventLogTitle') }}</h3>
        <button @click="fetchEvents" class="text-xs text-sky-600 hover:text-sky-800 font-medium cursor-pointer">
          {{ t('attendanceView.refresh') }}
        </button>
      </div>

      <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
        {{ t('status.loading', '載入中...') }}
      </div>
      <div v-else-if="events.length === 0" class="p-8 text-center text-xs text-text-muted">
        {{ t('attendanceView.noEvents') }}
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50/50 text-text-muted font-medium border-b border-border-main">
            <tr>
              <th class="px-4 py-3">{{ t('attendanceView.table.eventId') }}</th>
              <th class="px-4 py-3">{{ t('attendanceView.table.employeeNo') }}</th>
              <th class="px-4 py-3">{{ t('attendanceView.table.workDate') }}</th>
              <th class="px-4 py-3">{{ t('attendanceView.table.type') }}</th>
              <th class="px-4 py-3">{{ t('attendanceView.table.punchTime') }}</th>
              <th class="px-4 py-3">{{ t('attendanceView.table.source') }}</th>
              <th class="px-4 py-3">{{ t('attendanceView.table.status') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border-main">
            <tr v-for="e in events" :key="e.id" class="hover:bg-slate-50/50 transition">
              <td class="px-4 py-3 font-mono text-[11px] text-slate-500">{{ e.id.substring(0, 8) }}...</td>
              <td class="px-4 py-3 font-mono font-medium text-slate-800">{{ e.employee_id }}</td>
              <td class="px-4 py-3 font-mono text-slate-700">{{ e.work_date }}</td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 rounded font-semibold text-[11px]"
                  :class="e.event_type === 'CHECK_IN' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-sky-50 text-sky-700 border border-sky-200'"
                >
                  {{ e.event_type === 'CHECK_IN' ? t('attendanceView.table.checkInBadge') : t('attendanceView.table.checkOutBadge') }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono font-medium text-slate-800">
                {{ formatInTimezone(e.event_at, timezone) }}
              </td>
              <td class="px-4 py-3 text-slate-500">{{ e.device_id || 'WEB' }}</td>
              <td class="px-4 py-3">
                <span v-if="e.is_abnormal" class="px-2 py-0.5 rounded bg-rose-50 text-rose-700 font-semibold text-[10px] border border-rose-200">
                  {{ t('attendanceView.table.abnormal', { reason: e.abnormal_reason }) }}
                </span>
                <span v-else class="text-emerald-600 font-semibold text-[11px]">
                  {{ t('attendanceView.table.normal') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 批次匯入 Modal -->
    <div v-if="showImportModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">📤 {{ t('attendanceView.importModal.title') }}</h3>
          <button @click="showImportModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <FormField :label="t('attendanceView.importModal.csvLabel')" :hint="t('attendanceView.importModal.csvHint')">
            <textarea
              v-model="importCsvText"
              rows="6"
              class="w-full px-3 py-2 text-xs font-mono rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
            ></textarea>
          </FormField>
          <div v-if="importMessage" class="text-xs font-medium" :class="importMessage.startsWith('❌') ? 'text-rose-600' : 'text-emerald-600'">
            {{ importMessage }}
          </div>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showImportModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 cursor-pointer"
          >
            {{ t('attendanceView.importModal.cancel') }}
          </button>
          <button
            @click="doImport"
            :disabled="isImporting"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs cursor-pointer disabled:opacity-50"
          >
            {{ isImporting ? t('attendanceView.importModal.importing') : t('attendanceView.importModal.submit') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

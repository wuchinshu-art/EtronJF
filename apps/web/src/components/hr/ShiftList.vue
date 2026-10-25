<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import FormField from '../common/FormField.vue';
import { apiFetch } from '../../utils/auth';

interface ShiftItem {
  id: string;
  company_id: string;
  code: string;
  name: string;
  work_start_time: string;
  work_end_time: string;
  break_start_time?: string | null;
  break_end_time?: string | null;
  break_minutes: number;
  daily_standard_minutes: number;
  flex_minutes: number;
  is_overnight: boolean;
  timezone?: string;
}

const props = defineProps<{
  companyId: string;
  timezone?: string;
}>();

const { t } = useTranslation();

const shifts = ref<ShiftItem[]>([]);
const isLoading = ref(false);
const isSaving = ref(false);
const showModal = ref(false);
const isEditing = ref(false);
const editingShiftId = ref('');

const newShiftId = ref('');
const newCode = ref('');
const newName = ref('');
const workStartTime = ref('09:00');
const workEndTime = ref('18:00');
const breakStartTime = ref('12:00');
const breakEndTime = ref('13:00');
const breakMinutes = ref(60);
const flexMinutes = ref(30);
const dailyStandardMinutes = ref(480);
const isOvernight = ref(false);
const selectedShiftTimezone = ref('Asia/Taipei');
const errorMessage = ref('');

async function fetchShifts() {
  isLoading.value = true;
  try {
    const res = await fetch(`/api/v1/hr/shifts?company_id=${props.companyId}`);
    if (res.ok) {
      shifts.value = await res.json();
    }
  } catch {
    shifts.value = [];
  } finally {
    isLoading.value = false;
  }
}

function openCreateModal() {
  isEditing.value = false;
  editingShiftId.value = '';
  newShiftId.value = `SHIFT-${Date.now().toString().slice(-6)}`;
  newCode.value = 'NORMAL-FLEX';
  newName.value = '台北常規彈性班';
  workStartTime.value = '09:00';
  workEndTime.value = '18:00';
  breakStartTime.value = '12:00';
  breakEndTime.value = '13:00';
  breakMinutes.value = 60;
  flexMinutes.value = 30;
  dailyStandardMinutes.value = 480;
  isOvernight.value = false;
  selectedShiftTimezone.value = props.timezone || 'Asia/Taipei';
  errorMessage.value = '';
  showModal.value = true;
}

function openEditModal(s: ShiftItem) {
  isEditing.value = true;
  editingShiftId.value = s.id;
  newShiftId.value = s.id;
  newCode.value = s.code;
  newName.value = s.name;
  workStartTime.value = s.work_start_time || '09:00';
  workEndTime.value = s.work_end_time || '18:00';
  breakStartTime.value = s.break_start_time || '12:00';
  breakEndTime.value = s.break_end_time || '13:00';
  breakMinutes.value = s.break_minutes ?? 60;
  flexMinutes.value = s.flex_minutes ?? 0;
  dailyStandardMinutes.value = s.daily_standard_minutes ?? 480;
  isOvernight.value = !!s.is_overnight;
  selectedShiftTimezone.value = s.timezone || props.timezone || 'Asia/Taipei';
  errorMessage.value = '';
  showModal.value = true;
}

// 根據休息開始與結束時間自動計算休息分鐘數
function handleBreakTimeChange() {
  if (!breakStartTime.value || !breakEndTime.value) return;
  const [bsh, bsm] = breakStartTime.value.split(':').map(Number);
  const [beh, bem] = breakEndTime.value.split(':').map(Number);
  let span = (beh * 60 + bem) - (bsh * 60 + bsm);
  if (span < 0) span += 24 * 60;
  if (span > 0 && span <= 240) {
    breakMinutes.value = span;
  }
  autoCalculateMinutes();
}

// 自動試算標準每日工作工時
function autoCalculateMinutes() {
  if (!workStartTime.value || !workEndTime.value) return;
  const [sh, sm] = workStartTime.value.split(':').map(Number);
  const [eh, em] = workEndTime.value.split(':').map(Number);
  let totalSpan = (eh * 60 + em) - (sh * 60 + sm);
  if (isOvernight.value || totalSpan <= 0) {
    totalSpan += 24 * 60;
  }
  const netWork = Math.max(0, totalSpan - Number(breakMinutes.value || 0));
  dailyStandardMinutes.value = netWork;
}

// 計算彈性打卡區間字串
function getFlexRange(startTime: string, flex: number) {
  if (!startTime || !flex || flex <= 0) return t('hr.shifts.fixedSchedule');
  const [h, m] = startTime.split(':').map(Number);
  const totalM = h * 60 + m;
  const startM = totalM - flex;
  const endM = totalM + flex;

  const fmt = (mins: number) => {
    let normalized = (mins + 24 * 60) % (24 * 60);
    const rh = Math.floor(normalized / 60);
    const rm = normalized % 60;
    return `${String(rh).padStart(2, '0')}:${String(rm).padStart(2, '0')}`;
  };

  return `${fmt(startM)} ~ ${fmt(endM)} (${t('hr.shifts.flexMinutes', { minutes: flex })})`;
}

async function saveShift() {
  if (!newCode.value || !newName.value || !workStartTime.value || !workEndTime.value) {
    errorMessage.value = '請填寫班別代號、名稱與工作起訖時間';
    return;
  }

  isSaving.value = true;
  errorMessage.value = '';

  try {
    const payload = {
      code: newCode.value,
      name: newName.value,
      work_start_time: workStartTime.value,
      work_end_time: workEndTime.value,
      break_start_time: breakStartTime.value || null,
      break_end_time: breakEndTime.value || null,
      break_minutes: Number(breakMinutes.value || 60),
      daily_standard_minutes: Number(dailyStandardMinutes.value || 480),
      flex_minutes: Number(flexMinutes.value || 0),
      is_overnight: isOvernight.value,
      timezone: selectedShiftTimezone.value,
    };

    if (isEditing.value) {
      const res = await apiFetch(`/api/v1/hr/shifts/${editingShiftId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '更新班別失敗');
      }
    } else {
      if (!newShiftId.value) {
        errorMessage.value = '請填寫班別 ID';
        isSaving.value = false;
        return;
      }
      const res = await apiFetch('/api/v1/hr/shifts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: newShiftId.value,
          company_id: props.companyId,
          ...payload,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error?.message || err.message || '建立班別失敗');
      }
    }

    showModal.value = false;
    await fetchShifts();
  } catch (err: any) {
    errorMessage.value = err.message || '連線錯誤';
  } finally {
    isSaving.value = false;
  }
}

async function deleteShift(s: ShiftItem) {
  if (!confirm(t('hr.shifts.deleteConfirm', { name: s.name }))) {
    return;
  }

  try {
    const res = await apiFetch(`/api/v1/hr/shifts/${s.id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.error?.message || err.message || '刪除失敗');
      return;
    }
    await fetchShifts();
  } catch {
    alert('連線錯誤，無法刪除班別');
  }
}

watch(() => props.companyId, () => fetchShifts());
onMounted(() => fetchShifts());
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-semibold text-slate-800">⏱️ {{ t('hr.shifts.title') }}</h3>
        <p class="text-xs text-text-muted">{{ t('hr.shifts.subtitle') }}</p>
      </div>
      <button
        @click="openCreateModal"
        class="px-3.5 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-xs font-semibold text-white shadow-xs transition cursor-pointer"
      >
        {{ t('hr.shifts.createBtn') }}
      </button>
    </div>

    <!-- 班別清單 -->
    <div v-if="isLoading" class="p-8 text-center text-xs text-text-muted">
      {{ t('hr.shifts.loading') }}
    </div>
    <div v-else-if="shifts.length === 0" class="p-8 text-center text-xs text-text-muted bg-white rounded-xl border border-slate-200">
      {{ t('hr.shifts.empty') }}
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <div
        v-for="s in shifts"
        :key="s.id"
        class="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs hover:border-(--color-primary) hover:shadow-md transition flex flex-col justify-between"
      >
        <div>
          <!-- 卡片頂部標題與標籤 -->
          <div class="flex items-start justify-between mb-3">
            <div>
              <h4 class="text-sm font-bold text-slate-900 leading-snug">{{ s.name }}</h4>
              <span class="font-mono text-[11px] text-slate-400">{{ t('hr.shifts.code') }}: {{ s.code }}</span>
            </div>
            <div class="flex flex-col items-end space-y-1">
              <span
                class="text-[10px] font-semibold px-2.5 py-0.5 rounded-full"
                :class="s.is_overnight ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'"
              >
                {{ s.is_overnight ? t('hr.shifts.overnightShift') : t('hr.shifts.regularDayShift') }}
              </span>
              <span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 flex items-center space-x-1">
                <span>🌐</span>
                <span>{{ s.timezone === 'Asia/Tokyo' ? t('hr.shifts.tzTokyo') : t('hr.shifts.tzTaipei') }}</span>
              </span>
            </div>
          </div>

          <!-- 詳細工時資訊 -->
          <div class="space-y-2.5 text-xs text-slate-600 pt-1 border-t border-slate-100">
            <!-- 工作時間 -->
            <div class="flex items-center justify-between">
              <span class="flex items-center text-slate-500">
                <span class="mr-1.5">🕒</span> {{ t('hr.shifts.workTime') }}:
              </span>
              <span class="font-mono font-bold text-slate-800 text-sm">
                {{ s.work_start_time }} ~ {{ s.work_end_time }}
              </span>
            </div>

            <!-- 休息起訖時間 -->
            <div class="flex items-center justify-between">
              <span class="flex items-center text-slate-500">
                <span class="mr-1.5">☕</span> {{ t('hr.shifts.breakTime') }}:
              </span>
              <span class="font-mono font-semibold text-amber-700 bg-amber-50/60 px-2 py-0.5 rounded border border-amber-200/60 text-[11px]">
                {{ s.break_start_time || '12:00' }} ~ {{ s.break_end_time || '13:00' }} ({{ t('hr.shifts.breakMinutes', { minutes: s.break_minutes }) }})
              </span>
            </div>

            <!-- 彈性時間區間 -->
            <div class="flex items-center justify-between">
              <span class="flex items-center text-slate-500">
                <span class="mr-1.5">🎯</span> {{ t('hr.shifts.flexTime') }}:
              </span>
              <span class="font-mono font-semibold" :class="s.flex_minutes > 0 ? 'text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 text-[11px]' : 'text-slate-400'">
                {{ getFlexRange(s.work_start_time, s.flex_minutes) }}
              </span>
            </div>

            <!-- 標準工作工時 -->
            <div class="flex items-center justify-between">
              <span class="flex items-center text-slate-500">
                <span class="mr-1.5">⚖️</span> {{ t('hr.shifts.standardHours') }}:
              </span>
              <span class="font-mono font-bold text-slate-800">
                {{ s.daily_standard_minutes }} {{ t('hr.shifts.minutesUnit') }} ({{ (s.daily_standard_minutes / 60).toFixed(1) }} {{ t('hr.shifts.hoursUnit') }})
              </span>
            </div>
          </div>
        </div>

        <!-- 調整與操作按鈕 -->
        <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end space-x-2">
          <button
            @click="openEditModal(s)"
            class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200 transition cursor-pointer flex items-center space-x-1"
          >
            <span>✏️</span>
            <span>{{ t('actions.edit') }}</span>
          </button>
          <button
            @click="deleteShift(s)"
            class="px-2.5 py-1.5 text-xs font-semibold rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition cursor-pointer flex items-center space-x-1"
          >
            <span>🗑️</span>
            <span>{{ t('actions.delete') }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 新增 / 編輯班別 Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in">
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <h3 class="text-base font-semibold text-slate-800">
            {{ isEditing ? t('hr.shifts.modalEditTitle') : t('hr.shifts.modalCreateTitle') }}
          </h3>
          <button @click="showModal = false" class="text-slate-400 hover:text-slate-600 text-lg cursor-pointer">&times;</button>
        </div>

        <div class="p-6 space-y-4">
          <div v-if="errorMessage" class="p-3 text-xs rounded-lg bg-rose-50 text-rose-700 border border-rose-200">
            {{ errorMessage }}
          </div>

          <FormField :label="t('hr.shifts.code') + ' ID'" required>
            <input
              v-model="newShiftId"
              type="text"
              :disabled="isEditing"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              :class="isEditing ? 'bg-slate-100 text-slate-500 cursor-not-allowed' : 'bg-white'"
            />
          </FormField>

          <div class="grid grid-cols-2 gap-4">
            <FormField :label="t('hr.shifts.shiftCode')" required>
              <input
                v-model="newCode"
                type="text"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
            <FormField :label="t('hr.shifts.shiftName')" required>
              <input
                v-model="newName"
                type="text"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <!-- 適用時區選擇 -->
          <FormField :label="t('hr.shifts.timezone')" required>
            <select
              v-model="selectedShiftTimezone"
              class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:outline-hidden focus:ring-1 focus:ring-(--color-primary) cursor-pointer"
            >
              <option value="Asia/Taipei">{{ t('hr.shifts.tzTaipei') }}</option>
              <option value="Asia/Tokyo">{{ t('hr.shifts.tzTokyo') }}</option>
            </select>
          </FormField>

          <!-- 工作起訖時間 -->
          <div class="grid grid-cols-2 gap-4">
            <FormField label="上班時間 (HH:mm)" required>
              <input
                v-model="workStartTime"
                type="time"
                @change="autoCalculateMinutes"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
            <FormField label="下班時間 (HH:mm)" required>
              <input
                v-model="workEndTime"
                type="time"
                @change="autoCalculateMinutes"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
          </div>

          <!-- 休息起訖時間（從幾點到幾點） -->
          <div class="p-3 bg-amber-50/50 rounded-xl border border-amber-200/70 space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-amber-900">☕ 休息時間設定 (從幾點到幾點)</span>
              <span class="text-[11px] font-mono font-semibold text-amber-800">共 {{ breakMinutes }} 分鐘</span>
            </div>
            <div class="grid grid-cols-3 gap-3">
              <FormField label="休息起始 (HH:mm)">
                <input
                  v-model="breakStartTime"
                  type="time"
                  @change="handleBreakTimeChange"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                />
              </FormField>
              <FormField label="休息結束 (HH:mm)">
                <input
                  v-model="breakEndTime"
                  type="time"
                  @change="handleBreakTimeChange"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                />
              </FormField>
              <FormField label="折合休息分鐘數">
                <input
                  v-model.number="breakMinutes"
                  type="number"
                  @input="autoCalculateMinutes"
                  class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                />
              </FormField>
            </div>
          </div>

          <!-- 彈性時間設定 -->
          <div class="p-3 bg-sky-50/50 rounded-xl border border-sky-200/70 space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-sky-900">🎯 彈性時間設定 (Flex Time)</span>
              <span class="text-[11px] font-mono text-sky-800">
                {{ getFlexRange(workStartTime, flexMinutes) }}
              </span>
            </div>
            <div class="grid grid-cols-2 gap-3 items-center">
              <FormField label="彈性分鐘數 (前後寬限)" hint="例如 0, 15, 30, 60">
                <select
                  v-model.number="flexMinutes"
                  class="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                >
                  <option :value="0">0 分鐘 (固定打卡無彈性)</option>
                  <option :value="15">±15 分鐘 (前後彈性一刻鐘)</option>
                  <option :value="30">±30 分鐘 (前後彈性半小時)</option>
                  <option :value="60">±60 分鐘 (前後彈性一小時)</option>
                </select>
              </FormField>
              <div class="text-[11px] text-slate-500 pt-2 leading-relaxed">
                若上班設定為 {{ workStartTime }}，員工於彈性區間內打卡均屬正常出勤。
              </div>
            </div>
          </div>

          <!-- 標準工時試算折合 -->
          <div class="grid grid-cols-2 gap-4 items-center">
            <FormField label="標準工時分鐘數" required hint="8小時=480分">
              <input
                v-model.number="dailyStandardMinutes"
                type="number"
                class="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-(--color-primary)"
              />
            </FormField>
            <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col justify-center">
              <span class="text-[11px] text-slate-500">法定折合工時：</span>
              <span class="font-bold text-slate-900 font-mono text-sm">
                {{ (dailyStandardMinutes / 60).toFixed(2) }} 小時 / 日
              </span>
            </div>
          </div>

          <label class="flex items-center space-x-2 cursor-pointer pt-1">
            <input
              v-model="isOvernight"
              type="checkbox"
              @change="autoCalculateMinutes"
              class="w-4 h-4 rounded text-(--color-primary)"
            />
            <span class="text-xs text-slate-700 font-medium">是否為跨午夜夜班 (Overnight Shift，跨至翌日)</span>
          </label>
        </div>

        <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end space-x-2">
          <button
            @click="showModal = false"
            class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 transition cursor-pointer"
          >
            {{ t('actions.cancel') }}
          </button>
          <button
            @click="saveShift"
            :disabled="isSaving"
            class="px-4 py-2 text-xs font-semibold rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white shadow-xs transition cursor-pointer disabled:opacity-50"
          >
            {{ isSaving ? '儲存中...' : (isEditing ? '儲存調整' : '建立班別') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>



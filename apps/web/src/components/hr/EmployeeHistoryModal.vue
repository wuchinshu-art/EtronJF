<script setup lang="ts">
import { ref, watch } from 'vue';
import { useTranslation } from 'i18next-vue';

interface ChangeRecord {
  id: string;
  change_type: string;
  effective_date: string;
  before_organization_id: string | null;
  after_organization_id: string | null;
  notes: string | null;
  created_at: string;
}

const props = defineProps<{
  isOpen: boolean;
  employee: {
    id: string;
    employee_no: string;
    full_name: string;
  } | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const { t } = useTranslation();

const changes = ref<ChangeRecord[]>([]);
const isLoading = ref(false);

async function fetchChanges() {
  if (!props.employee) return;
  isLoading.value = true;
  try {
    const res = await fetch(`/api/v1/hr/employees/${props.employee.id}/changes`);
    if (res.ok) {
      changes.value = await res.json();
    }
  } catch {
    changes.value = [];
  } finally {
    isLoading.value = false;
  }
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) fetchChanges();
  }
);
</script>

<template>
  <div v-if="props.isOpen && props.employee" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden animate-fade-in flex flex-col max-h-[85vh]">
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <h3 class="text-base font-semibold text-slate-800 flex items-center">
          <span class="mr-2">📜</span> {{ t('hr.employeeHistoryModal.title') }}
        </h3>
        <button @click="emit('close')" class="text-slate-400 hover:text-slate-600 text-lg">&times;</button>
      </div>

      <div class="p-6 overflow-y-auto flex-1">
        <div class="mb-4 text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200">
          {{ t('hr.employeeHistoryModal.employeeLabel') }}: <strong class="text-slate-800">{{ props.employee.full_name }}</strong> ({{ props.employee.employee_no }})
        </div>

        <div v-if="isLoading" class="text-center py-8 text-xs text-slate-400">
          {{ t('hr.employeeHistoryModal.loading') }}
        </div>

        <div v-else-if="changes.length === 0" class="text-center py-8 text-xs text-slate-400">
          {{ t('hr.employeeHistoryModal.noHistory') }}
        </div>

        <div v-else class="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
          <div v-for="ch in changes" :key="ch.id" class="relative">
            <!-- 圓點 -->
            <div
              class="absolute -left-6 top-1 w-3 h-3 rounded-full border-2 border-white ring-2"
              :class="{
                'bg-emerald-500 ring-emerald-100': ch.change_type === 'ONBOARD',
                'bg-sky-500 ring-sky-100': ch.change_type === 'TRANSFER',
                'bg-rose-500 ring-rose-100': ch.change_type === 'RESIGN',
                'bg-amber-500 ring-amber-100': ch.change_type === 'PROMOTION',
              }"
            ></div>

            <div class="bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs space-y-1">
              <div class="flex items-center justify-between">
                <span
                  class="font-semibold px-2 py-0.5 rounded text-[10px]"
                  :class="{
                    'bg-emerald-100 text-emerald-800': ch.change_type === 'ONBOARD',
                    'bg-sky-100 text-sky-800': ch.change_type === 'TRANSFER',
                    'bg-rose-100 text-rose-800': ch.change_type === 'RESIGN',
                    'bg-amber-100 text-amber-800': ch.change_type === 'PROMOTION',
                  }"
                >
                  {{ ch.change_type === 'ONBOARD' ? t('hr.employeeHistoryModal.onboard') : ch.change_type === 'TRANSFER' ? t('hr.employeeHistoryModal.transfer') : ch.change_type === 'RESIGN' ? t('hr.employeeHistoryModal.resign') : ch.change_type === 'PROMOTION' ? t('hr.employeeHistoryModal.promotion') : ch.change_type }}
                </span>
                <span class="text-[11px] font-mono text-slate-500">{{ ch.effective_date }}</span>
              </div>
              <p v-if="ch.notes" class="text-slate-700 pt-1">{{ ch.notes }}</p>
              <div class="text-[10px] text-slate-400 pt-1 font-mono">
                {{ ch.created_at ? new Date(ch.created_at).toLocaleString() : '' }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end">
        <button
          @click="emit('close')"
          type="button"
          class="px-4 py-2 text-xs font-medium rounded-lg border border-slate-300 hover:bg-white text-slate-700 transition cursor-pointer"
        >
          {{ t('actions.close') }}
        </button>
      </div>
    </div>
  </div>
</template>

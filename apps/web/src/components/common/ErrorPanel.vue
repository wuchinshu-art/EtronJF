<script setup lang="ts">
import { ref } from 'vue';

export interface FieldErrorItem {
  field: string;
  message: string;
}

const props = defineProps<{
  code?: string;
  message: string;
  fieldErrors?: FieldErrorItem[];
  requestId?: string;
}>();

const emit = defineEmits<{
  (e: 'retry'): void;
}>();

const copied = ref(false);

function copyRequestId() {
  if (props.requestId) {
    navigator.clipboard.writeText(props.requestId);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  }
}
</script>

<template>
  <div class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-900 shadow-xs mb-4">
    <div class="flex items-start justify-between">
      <div class="flex items-start space-x-2.5">
        <span class="text-rose-600 text-base leading-none">⚠️</span>
        <div>
          <h4 class="font-bold text-rose-950">
            <span v-if="code" class="font-mono bg-rose-100 px-1 py-0.5 rounded text-[10px] mr-1">[{{ code }}]</span>
            {{ message }}
          </h4>
          
          <!-- Field Errors list -->
          <ul v-if="fieldErrors && fieldErrors.length" class="mt-2 space-y-1 list-disc list-inside text-rose-800">
            <li v-for="(fe, i) in fieldErrors" :key="i">
              <span class="font-semibold">{{ fe.field }}:</span> {{ fe.message }}
            </li>
          </ul>

          <!-- Request ID & Traceability -->
          <div v-if="requestId" class="mt-2 text-[10px] text-rose-600 flex items-center space-x-2">
            <span>Request ID: <span class="font-mono select-all">{{ requestId }}</span></span>
            <button
              @click="copyRequestId"
              class="underline hover:text-rose-800 transition focus:outline-hidden"
            >
              {{ copied ? '已複製' : '複製追蹤碼' }}
            </button>
          </div>
        </div>
      </div>

      <button
        @click="emit('retry')"
        class="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white font-medium transition"
      >
        重試
      </button>
    </div>
  </div>
</template>

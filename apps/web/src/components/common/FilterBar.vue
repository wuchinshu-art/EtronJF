<script setup lang="ts">
import { ref } from 'vue';
import { useTranslation } from 'i18next-vue';

defineProps<{
  keywordPlaceholder?: string;
}>();

const emit = defineEmits<{
  (e: 'search', keyword: string): void;
  (e: 'reset'): void;
}>();

const { t } = useTranslation();
const keyword = ref('');

function onSearch() {
  emit('search', keyword.value);
}

function onReset() {
  keyword.value = '';
  emit('reset');
}
</script>

<template>
  <div class="bg-white rounded-xl border border-border-main p-4 shadow-xs mb-4 flex flex-wrap items-center justify-between gap-3 text-xs">
    <div class="flex flex-wrap items-center gap-3 flex-1">
      <!-- Search Input -->
      <div class="relative min-w-50 flex-1 max-w-xs">
        <input
          v-model="keyword"
          type="text"
          :placeholder="keywordPlaceholder || t('actions.search')"
          @keydown.enter="onSearch"
          class="w-full pl-8 pr-3 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-hidden focus:border-(--color-primary) transition"
        />
        <span class="absolute left-2.5 top-2 text-slate-400">🔍</span>
      </div>

      <!-- Custom Filter Slots -->
      <slot />
    </div>

    <!-- Actions -->
    <div class="flex items-center space-x-2">
      <button
        @click="onSearch"
        class="px-3 py-1.5 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white font-medium transition cursor-pointer"
      >
        {{ t('actions.search') }}
      </button>
      <button
        @click="onReset"
        class="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-medium transition cursor-pointer"
      >
        {{ t('actions.reset') }}
      </button>
    </div>
  </div>
</template>

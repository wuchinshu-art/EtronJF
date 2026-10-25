<script setup lang="ts">
defineProps<{
  title?: string;
  description?: string;
  icon?: string;
}>();
</script>

<template>
  <div class="text-center py-12 px-4 rounded-xl border border-dashed border-slate-300 bg-white">
    <div class="text-3xl mb-2">{{ icon || '📭' }}</div>
    <h3 class="text-sm font-semibold text-slate-800">
      {{ title || '目前尚無任何資料' }}
    </h3>
    <p v-if="description" class="text-xs text-text-muted mt-1 max-w-sm mx-auto">
      {{ description }}
    </p>
    <div class="mt-4 flex justify-center space-x-2">
      <slot />
    </div>
  </div>
</template>

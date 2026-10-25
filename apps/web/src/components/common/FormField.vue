<script setup lang="ts">
defineProps<{
  label?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  id?: string;
}>();
</script>

<template>
  <div class="mb-4 text-xs">
    <label
      v-if="label"
      :for="id"
      class="block font-medium text-slate-700 mb-1 break-words"
    >
      {{ label }}
      <span v-if="required" class="text-red-500 font-bold ml-0.5">*</span>
    </label>

    <div>
      <slot />
    </div>

    <!-- Error message -->
    <p v-if="error" class="mt-1 text-xs text-red-600 font-medium">
      {{ error }}
    </p>

    <!-- Hint message -->
    <p v-else-if="hint" class="mt-1 text-xs text-text-muted">
      {{ hint }}
    </p>
  </div>
</template>

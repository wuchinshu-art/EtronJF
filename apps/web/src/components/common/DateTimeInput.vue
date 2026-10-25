<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string;
    mode?: 'date' | 'datetime';
    timezone?: string;
    disabled?: boolean;
  }>(),
  {
    mode: 'date',
    timezone: 'Asia/Taipei',
    disabled: false,
  }
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

function onInput(e: Event) {
  const target = e.target as HTMLInputElement;
  emit('update:modelValue', target.value);
}
</script>

<template>
  <div class="relative flex items-center">
    <input
      :type="mode === 'datetime' ? 'datetime-local' : 'date'"
      :value="modelValue"
      :disabled="disabled"
      @input="onInput"
      class="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-lg text-slate-800 focus:outline-hidden focus:border-(--color-primary) disabled:bg-slate-50 transition"
    />
    <span v-if="mode === 'datetime' && timezone" class="ml-2 text-[10px] text-text-muted whitespace-nowrap">
      ({{ timezone === 'Asia/Tokyo' ? '東京' : '台北' }})
    </span>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: string | number;
    currency?: string;
    currencies?: string[];
    disabled?: boolean;
    placeholder?: string;
  }>(),
  {
    currency: 'TWD',
    currencies: () => ['TWD', 'JPY', 'USD'],
    disabled: false,
    placeholder: '0.00',
  }
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'update:currency', currency: string): void;
}>();

function onInput(event: Event) {
  const target = event.target as HTMLInputElement;
  // 濾除非數字與小數點，防止非法字元
  const sanitized = target.value.replace(/[^0-9.]/g, '');
  emit('update:modelValue', sanitized);
}

function onCurrencyChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  emit('update:currency', target.value);
}
</script>

<template>
  <div class="relative flex rounded-lg shadow-xs border border-slate-300 focus-within:border-(--color-primary) overflow-hidden bg-white text-xs">
    <!-- Currency Selector Prefix -->
    <select
      :value="currency"
      :disabled="disabled"
      @change="onCurrencyChange"
      class="bg-slate-100 px-2.5 py-1.5 border-r border-slate-300 text-slate-700 font-semibold focus:outline-hidden cursor-pointer"
    >
      <option v-for="c in currencies" :key="c" :value="c">
        {{ c }}
      </option>
    </select>

    <!-- Decimal Amount Input -->
    <input
      type="text"
      inputmode="decimal"
      :value="modelValue"
      :disabled="disabled"
      :placeholder="placeholder"
      @input="onInput"
      class="w-full px-3 py-1.5 text-right font-mono text-slate-800 focus:outline-hidden disabled:bg-slate-50"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    status: string;
    label?: string;
  }>(),
  {}
);

const badgeStyle = computed(() => {
  switch (props.status.toLowerCase()) {
    case 'approved':
    case 'healthy':
    case 'success':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'in_review':
    case 'pending':
    case 'submitted':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'rejected':
    case 'cancelled':
    case 'error':
    case 'unhealthy':
      return 'bg-rose-50 text-rose-700 border-rose-200';
    case 'returned':
      return 'bg-purple-50 text-purple-700 border-purple-200';
    case 'draft':
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200';
  }
});
</script>

<template>
  <span
    :class="[
      'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border',
      badgeStyle,
    ]"
  >
    <slot>{{ label || status }}</slot>
  </span>
</template>

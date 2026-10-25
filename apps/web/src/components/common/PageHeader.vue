<script setup lang="ts">
defineProps<{
  title: string;
  subtitle?: string;
  breadcrumbs?: Array<{ label: string; href?: string }>;
}>();
</script>

<template>
  <div class="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border-main pb-4">
    <div>
      <nav v-if="breadcrumbs && breadcrumbs.length" class="flex text-xs text-text-muted mb-1 space-x-1">
        <template v-for="(bc, index) in breadcrumbs" :key="index">
          <span v-if="index > 0" class="mx-1">/</span>
          <a v-if="bc.href" :href="bc.href" class="hover:text-(--color-primary) transition">{{ bc.label }}</a>
          <span v-else class="text-slate-700 font-medium">{{ bc.label }}</span>
        </template>
      </nav>
      <h2 class="text-xl font-bold text-text-main tracking-tight">
        {{ title }}
      </h2>
      <p v-if="subtitle" class="text-xs text-text-muted mt-0.5">
        {{ subtitle }}
      </p>
    </div>

    <!-- Action Slot (Buttons, Search, etc.) -->
    <div class="flex items-center space-x-2">
      <slot name="actions" />
    </div>
  </div>
</template>

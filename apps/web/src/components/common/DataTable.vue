<script setup lang="ts">
import { useTranslation } from 'i18next-vue';

export interface TableColumn {
  key: string;
  label: string;
  sortable?: boolean;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

withDefaults(
  defineProps<{
    columns: TableColumn[];
    rows: any[];
    loading?: boolean;
    currentPage?: number;
    pageSize?: number;
    totalCount?: number;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
  }>(),
  {
    loading: false,
    currentPage: 1,
    pageSize: 10,
    totalCount: 0,
    sortBy: '',
    sortOrder: 'asc',
  }
);

const emit = defineEmits<{
  (e: 'sort-change', key: string): void;
  (e: 'page-change', page: number): void;
}>();

const { t } = useTranslation();

function onSort(column: TableColumn) {
  if (column.sortable) {
    emit('sort-change', column.key);
  }
}
</script>

<template>
  <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden flex flex-col">
    <!-- Horizontal Scrollable Table Wrapper -->
    <div class="overflow-x-auto min-w-full">
      <table class="min-w-full divide-y divide-border-main text-left text-xs">
        <thead class="bg-slate-50 text-text-muted font-semibold uppercase tracking-wider">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="[
                'px-4 py-3 select-none',
                col.sortable ? 'cursor-pointer hover:bg-slate-100 transition' : '',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
              ]"
              :style="{ width: col.width }"
              @click="onSort(col)"
            >
              <div class="inline-flex items-center space-x-1">
                <span>{{ col.label }}</span>
                <span v-if="col.sortable" class="text-slate-400">
                  <span v-if="sortBy === col.key && sortOrder === 'asc'">▲</span>
                  <span v-else-if="sortBy === col.key && sortOrder === 'desc'">▼</span>
                  <span v-else>⇅</span>
                </span>
              </div>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-border-main bg-white">
          <tr v-if="loading">
            <td :colspan="columns.length" class="px-4 py-12 text-center text-slate-500">
              <div class="inline-flex items-center space-x-2">
                <span class="animate-spin text-lg">⏳</span>
                <span>{{ t('status.loading') }}</span>
              </div>
            </td>
          </tr>

          <tr v-else-if="!rows || rows.length === 0">
            <td :colspan="columns.length" class="px-4 py-12 text-center text-slate-400">
              <slot name="empty">{{ t('table.empty') }}</slot>
            </td>
          </tr>

          <tr
            v-else
            v-for="(row, idx) in rows"
            :key="row.id || idx"
            class="hover:bg-slate-50 transition"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="[
                'px-4 py-3 text-slate-800 whitespace-nowrap',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
              ]"
            >
              <slot :name="col.key" :row="row">
                {{ row[col.key] }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination Footer -->
    <div
      v-if="totalCount > 0"
      class="px-4 py-3 bg-slate-50 border-t border-border-main flex items-center justify-between text-xs text-slate-600"
    >
      <div>
        {{ t('table.totalRecords', { total: totalCount, page: currentPage }) }}
      </div>
      <div class="flex items-center space-x-1">
        <button
          :disabled="currentPage <= 1"
          @click="emit('page-change', currentPage - 1)"
          class="px-2.5 py-1 rounded border border-slate-300 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer"
        >
          {{ t('actions.prevPage') }}
        </button>
        <button
          :disabled="currentPage * pageSize >= totalCount"
          @click="emit('page-change', currentPage + 1)"
          class="px-2.5 py-1 rounded border border-slate-300 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition cursor-pointer"
        >
          {{ t('actions.nextPage') }}
        </button>
      </div>
    </div>
  </div>
</template>

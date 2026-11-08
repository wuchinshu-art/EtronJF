<script setup lang="ts">
import { computed } from 'vue';
import { useTranslation } from 'i18next-vue';
import PageHeader from '../common/PageHeader.vue';
import EmptyState from '../common/EmptyState.vue';
import MySessionsPanel from './MySessionsPanel.vue';
import { currentUser } from '../../utils/auth';
import { visiblePortalModules } from '../../utils/portal';

const props = defineProps<{ timezone: string; company: string }>();
const emit = defineEmits<{ (e: 'open-module', key: string): void }>();
const { t } = useTranslation();

// Portal 首頁本身不列為模組卡片
const modules = computed(() => visiblePortalModules().filter((m) => m.key !== 'dashboard'));
</script>

<template>
  <div class="space-y-6" v-if="currentUser">
    <PageHeader
      :title="t('portal.welcome', { name: currentUser.display_name })"
      :subtitle="t('portal.subtitle')"
      :breadcrumbs="[{ label: t('appName') }, { label: t('nav.dashboard') }]"
    />

    <div class="grid gap-6 lg:grid-cols-3">
      <!-- 模組卡片 -->
      <section class="lg:col-span-2 space-y-3">
        <h3 class="text-sm font-bold text-text-main">{{ t('portal.modulesTitle') }}</h3>
        <EmptyState v-if="!modules.length" icon="🔒" :title="t('portal.noModules')" />
        <div v-else class="grid gap-3 grid-cols-2 sm:grid-cols-3" data-testid="portal-modules">
          <button
            v-for="m in modules"
            :key="m.key"
            @click="emit('open-module', m.key)"
            class="group text-left p-4 bg-white rounded-2xl border border-border-main shadow-xs hover:border-(--color-primary) hover:shadow-md focus:outline-hidden focus:ring-2 focus:ring-(--color-primary) transition cursor-pointer"
            :data-module="m.key"
          >
            <div class="text-2xl mb-2" aria-hidden="true">{{ m.icon }}</div>
            <div class="text-sm font-semibold text-text-main">{{ t(m.labelKey) }}</div>
            <div class="text-xs text-(--color-primary) mt-1 opacity-0 group-hover:opacity-100 transition">
              {{ t('portal.open') }} →
            </div>
          </button>
        </div>
      </section>

      <!-- 我的帳號 -->
      <section class="bg-white rounded-2xl border border-border-main shadow-xs p-5 space-y-3 text-xs" data-testid="portal-profile">
        <h3 class="text-sm font-bold text-text-main">{{ t('portal.profileTitle') }}</h3>
        <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
          <dt class="text-text-muted">{{ t('portal.usernameLabel') }}</dt>
          <dd class="font-mono text-text-main break-all">{{ currentUser.username }}</dd>
          <dt class="text-text-muted">{{ t('portal.emailLabel') }}</dt>
          <dd class="text-text-main break-all">{{ currentUser.email }}</dd>
          <dt class="text-text-muted">{{ t('portal.companyLabel') }}</dt>
          <dd class="font-mono text-text-main">{{ props.company || currentUser.active_company_id }}</dd>
          <dt class="text-text-muted">{{ t('portal.departmentLabel') }}</dt>
          <dd class="text-text-main">
            {{ currentUser.department_name || (currentUser.employee_id ? '-' : t('portal.notLinked')) }}
          </dd>
          <dt class="text-text-muted">{{ t('portal.managerLabel') }}</dt>
          <dd class="text-text-main">{{ currentUser.manager_name || '-' }}</dd>
          <dt class="text-text-muted">{{ t('portal.rolesLabel') }}</dt>
          <dd class="flex flex-wrap gap-1">
            <span
              v-for="r in currentUser.roles"
              :key="r"
              class="px-1.5 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200 font-mono text-[10px]"
            >{{ r }}</span>
            <span v-if="!currentUser.roles.length">-</span>
          </dd>
        </dl>
      </section>
    </div>

    <MySessionsPanel :timezone="props.timezone" />
  </div>
</template>

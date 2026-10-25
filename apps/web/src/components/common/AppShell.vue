<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useTranslation } from 'i18next-vue';
import { TIMEZONES } from '../../utils/time';
import {
  currentUser,
  showLoginModal,
  showChangePasswordModal,
  logout,
  hasAnyPermission,
} from '../../utils/auth';
import {
  availableCompanies,
  activeCompanyId,
  fetchAvailableCompanies,
  setActiveCompany,
} from '../../utils/companies';

const props = withDefaults(
  defineProps<{
    currentModule?: string;
  }>(),
  {
    currentModule: 'dashboard',
  }
);

interface NavItem {
  key: string;
  icon: string;
  labelKey: string;
  permissions?: string[];
  public?: boolean;
}

const navItems: NavItem[] = [
  { key: 'dashboard', icon: '📊', labelKey: 'nav.dashboard', public: true },
  {
    key: 'hr',
    icon: '👥',
    labelKey: 'nav.hr',
    permissions: ['hr.employee.manage', 'hr.org.manage', 'hr.shift.manage', 'hr.ledger.manage'],
  },
  {
    key: 'leave',
    icon: '🌴',
    labelKey: 'nav.leave',
    permissions: ['leave.create', 'leave.approve', 'leave.cancel'],
  },
  {
    key: 'attendance',
    icon: '⏱️',
    labelKey: 'nav.attendance',
    permissions: ['attendance.punch', 'attendance.manage'],
  },
  {
    key: 'travel',
    icon: '✈️',
    labelKey: 'nav.travel',
    permissions: ['travel.create', 'travel.approve', 'travel.settle', 'travel.finance'],
  },
  {
    key: 'expense',
    icon: '🧾',
    labelKey: 'nav.expense',
    permissions: ['expense.create', 'expense.approve'],
  },
  {
    key: 'seal',
    icon: '🔏',
    labelKey: 'nav.seal',
    permissions: ['seal.request', 'seal.approve', 'seal.execute', 'seal.master'],
  },
  {
    key: 'payment',
    icon: '💵',
    labelKey: 'nav.payment',
    permissions: ['payment.create', 'payment.approve', 'payment.finance', 'vendor.manage'],
  },
  {
    key: 'contract',
    icon: '📜',
    labelKey: 'nav.contract',
    permissions: ['contract.create', 'contract.approve', 'contract.archive'],
  },
  {
    key: 'users',
    icon: '🛡️',
    labelKey: 'nav.users',
    permissions: ['system.user.manage', 'system.role.manage'],
  },
];

const visibleNavItems = computed(() => {
  return navItems.filter((item) => {
    if (!currentUser.value) {
      return !!item.public;
    }
    if (currentUser.value.roles?.includes('ADMIN')) {
      return true;
    }
    if (!item.permissions || item.permissions.length === 0) {
      return true;
    }
    return hasAnyPermission(item.permissions);
  });
});

const { t, i18next } = useTranslation();

const isSidebarOpen = ref(true);
const isUserMenuOpen = ref(false);
const selectedTimezone = ref<string>(localStorage.getItem('etj_timezone') || TIMEZONES.TAIPEI);

const emit = defineEmits<{
  (e: 'change-timezone', tz: string): void;
  (e: 'change-company', comp: string): void;
  (e: 'select-module', module: string): void;
}>();

// 當登入之 active_company_id 變動時同步
watch(
  () => currentUser.value?.active_company_id,
  (comp) => {
    if (comp) {
      setActiveCompany(comp);
      emit('change-company', comp);
    }
  }
);

onMounted(() => {
  fetchAvailableCompanies();
  emit('change-company', activeCompanyId.value);
});

function setTimezone(tz: string) {
  selectedTimezone.value = tz;
  localStorage.setItem('etj_timezone', tz);
  emit('change-timezone', tz);
}

function handleCompanyChange() {
  setActiveCompany(activeCompanyId.value);
  emit('change-company', activeCompanyId.value);
}

function handleTimezoneChange() {
  setTimezone(selectedTimezone.value);
}

async function setLanguage(lang: string) {
  await i18next.changeLanguage(lang);
}

async function handleLanguageSelectChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  await setLanguage(target.value);
}

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value;
}

function selectModule(mod: string) {
  emit('select-module', mod);
}

async function handleLogout() {
  isUserMenuOpen.value = false;
  await logout();
}

function openChangePassword() {
  isUserMenuOpen.value = false;
  showChangePasswordModal.value = true;
}
</script>

<template>
  <div class="min-h-screen bg-(--color-surface-bg) flex flex-col font-sans">
    <!-- Top Navigation Bar -->
    <header class="bg-white border-b border-border-main sticky top-0 z-30 shadow-xs">
      <div class="px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <button
            @click="toggleSidebar"
            class="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 focus:outline-hidden cursor-pointer"
            title="切換側邊欄"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div class="w-8 h-8 rounded-lg bg-(--color-primary) flex items-center justify-center text-white font-bold text-sm shadow-xs">
            ETJ
          </div>
          <div>
            <h1 class="text-sm font-semibold text-text-main leading-tight">
              {{ t('appName') }}
            </h1>
            <p class="text-xs text-text-muted leading-none">
              {{ t('systemSubtitle') }}
            </p>
          </div>
        </div>

        <!-- Top Right Controls (Company, Timezone, Language, User Menu) -->
        <div class="flex items-center space-x-2.5">
          <!-- Company Selector (動態綁定法人公司基本資料) -->
          <div class="hidden sm:flex items-center space-x-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1">
            <span class="text-text-muted font-medium">🏢 {{ t('header.company') }}:</span>
            <select
              v-model="activeCompanyId"
              @change="handleCompanyChange"
              class="bg-transparent text-slate-800 font-semibold focus:outline-hidden cursor-pointer max-w-48 truncate"
            >
              <option
                v-for="comp in availableCompanies"
                :key="comp.id"
                :value="comp.id"
              >
                {{ comp.name }} ({{ comp.default_currency }})
              </option>
            </select>
          </div>

          <!-- Timezone Dropdown Selector -->
          <div class="flex items-center space-x-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1">
            <span class="text-text-muted font-medium">🌐 {{ t('header.timezone') }}:</span>
            <select
              v-model="selectedTimezone"
              @change="handleTimezoneChange"
              class="bg-transparent text-slate-800 font-semibold focus:outline-hidden cursor-pointer"
            >
              <option :value="TIMEZONES.TAIPEI">台北 (UTC+8)</option>
              <option :value="TIMEZONES.TOKYO">東京 (UTC+9)</option>
            </select>
          </div>

          <!-- Language Dropdown Selector -->
          <div class="flex items-center space-x-1.5 text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1">
            <span class="text-text-muted font-medium">🗣️ {{ t('header.language') }}:</span>
            <select
              :value="i18next.language"
              @change="handleLanguageSelectChange"
              class="bg-transparent text-slate-800 font-semibold focus:outline-hidden cursor-pointer"
            >
              <option value="zh-TW">繁體中文</option>
              <option value="ja-JP">日本語</option>
              <option value="en-US">English</option>
              <option value="zh-CN">简体中文</option>
            </select>
          </div>

          <!-- User Profile & Auth Status Section -->
          <div class="relative pl-2 border-l border-slate-200">
            <!-- 登入狀態 -->
            <div v-if="currentUser" class="flex items-center">
              <button
                @click="isUserMenuOpen = !isUserMenuOpen"
                class="flex items-center space-x-2 p-1.5 rounded-lg hover:bg-slate-100 transition focus:outline-hidden cursor-pointer"
              >
                <div class="w-7 h-7 rounded-full bg-blue-600 text-white font-semibold text-xs flex items-center justify-center shadow-xs">
                  {{ currentUser.display_name ? currentUser.display_name[0] : 'U' }}
                </div>
                <div class="text-left hidden md:block">
                  <div class="text-xs font-semibold text-slate-800 leading-tight">
                    {{ currentUser.display_name }}
                  </div>
                  <div class="text-[10px] text-slate-400 font-mono leading-none">
                    {{ currentUser.username }}
                  </div>
                </div>
                <svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              <!-- 下拉選單 -->
              <div
                v-if="isUserMenuOpen"
                class="absolute right-0 top-full mt-1.5 w-48 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50 animate-fade-in text-xs"
              >
                <div class="px-3.5 py-2 border-b border-slate-100">
                  <p class="font-semibold text-slate-800">{{ currentUser.display_name }}</p>
                  <p class="text-[11px] text-slate-400 truncate">{{ currentUser.email }}</p>
                  <div class="mt-1 flex flex-wrap gap-1">
                    <span
                      v-for="role in currentUser.roles"
                      :key="role"
                      class="px-1.5 py-0.2 bg-blue-50 text-blue-700 text-[10px] rounded font-mono"
                    >
                      {{ role }}
                    </span>
                  </div>
                </div>

                <button
                  @click="openChangePassword"
                  class="w-full text-left px-3.5 py-2 hover:bg-slate-50 flex items-center space-x-2 text-slate-700 cursor-pointer"
                >
                  <span>🔐</span>
                  <span>{{ t('auth.changePassword') }}</span>
                </button>

                <div class="border-t border-slate-100 my-1"></div>

                <button
                  @click="handleLogout"
                  class="w-full text-left px-3.5 py-2 hover:bg-rose-50 text-rose-600 flex items-center space-x-2 cursor-pointer font-medium"
                >
                  <span>🚪</span>
                  <span>{{ t('auth.logout') }}</span>
                </button>
              </div>
            </div>

            <!-- 未登入狀態 -->
            <div v-else>
              <button
                @click="showLoginModal = true"
                class="px-3 py-1.5 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs transition flex items-center space-x-1.5 cursor-pointer"
              >
                <span>🔑</span>
                <span>{{ t('auth.login') }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Body Layout: Sidebar + Main Content -->
    <div class="flex flex-1 overflow-hidden" @click="isUserMenuOpen = false">
      <!-- Sidebar -->
      <aside
        v-show="isSidebarOpen"
        class="w-64 bg-white border-r border-border-main shrink-0 flex flex-col justify-between transition-all duration-200"
      >
        <div class="p-4 space-y-1">
          <div class="text-xs font-semibold text-text-muted uppercase tracking-wider px-3 mb-2">
            {{ t('nav.modules') }}
          </div>
          <button
            v-for="item in visibleNavItems"
            :key="item.key"
            @click="selectModule(item.key)"
            class="w-full flex items-center px-3 py-2 text-sm font-medium rounded-lg transition cursor-pointer"
            :class="props.currentModule === item.key ? 'text-white bg-(--color-primary)' : 'text-slate-700 hover:bg-slate-100'"
          >
            <span class="mr-3">{{ item.icon }}</span> {{ t(item.labelKey) }}
          </button>
        </div>
      </aside>

      <!-- Main Scrollable Area -->
      <main class="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <slot :timezone="selectedTimezone" :company="activeCompanyId" :currentModule="props.currentModule" />
      </main>
    </div>
  </div>
</template>

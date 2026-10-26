<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useTranslation } from 'i18next-vue';
import { hasPermission } from '../../utils/auth';

const { t } = useTranslation();

// 權限檢查
const canManageUsers = computed(() => hasPermission('system.user.manage'));
const canManageRoles = computed(() => hasPermission('system.role.manage'));

// 標籤頁狀態：'users' | 'roles'
const activeTab = ref<'users' | 'roles'>('users');

watch([canManageUsers, canManageRoles], ([canUsers, canRoles]) => {
  if (!canUsers && canRoles) {
    activeTab.value = 'roles';
  } else if (canUsers && !canRoles) {
    activeTab.value = 'users';
  }
}, { immediate: true });

interface RoleMeta {
  id: string;
  name: string;
  description: string;
  is_system: boolean;
  permissions_count: number;
  users_count: number;
}

interface PermissionGroup {
  module: string;
  name: string;
  permissions: {
    code: string;
    name: string;
    description: string;
  }[];
}

interface UserItem {
  id: string;
  username: string;
  display_name: string;
  email: string;
  is_active: boolean;
  must_change_password: boolean;
  active_company_id: string | null;
  employee_id: string | null;
  employee_no: string | null;
  roles: string[];
  created_at: string;
}

interface CompanyItem {
  id: string;
  name: string;
}

interface EmployeeItem {
  id: string;
  employee_no: string;
  full_name: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  department_name?: string;
}

const props = defineProps<{
  companyId: string;
  timezone: string;
}>();


// 資料載入與訊息狀態
const loadingUsers = ref(false);
const loadingRoles = ref(false);
const savingRolePermissions = ref(false);
const toastMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null);

function showToast(text: string, type: 'success' | 'error' = 'success') {
  toastMessage.value = { type, text };
  setTimeout(() => {
    if (toastMessage.value?.text === text) {
      toastMessage.value = null;
    }
  }, 4000);
}

// ----------------------------------------------------
// Tab 1: 帳號管理相關 State 與邏輯
// ----------------------------------------------------
const users = ref<UserItem[]>([]);
const searchKeyword = ref('');
const filterRole = ref('');
const filterStatus = ref('');
const companies = ref<CompanyItem[]>([]);
const employees = ref<EmployeeItem[]>([]);

// 統計數據
const totalUsersCount = computed(() => users.value.length);
const activeUsersCount = computed(() => users.value.filter((u) => u.is_active).length);
const suspendedUsersCount = computed(() => users.value.filter((u) => !u.is_active).length);
const mustChangePwdCount = computed(() => users.value.filter((u) => u.must_change_password).length);

// 篩選後使用者列表
const filteredUsers = computed(() => {
  return users.value.filter((u) => {
    if (searchKeyword.value) {
      const q = searchKeyword.value.toLowerCase();
      const matchName = u.display_name.toLowerCase().includes(q);
      const matchUser = u.username.toLowerCase().includes(q);
      const matchEmail = u.email.toLowerCase().includes(q);
      const matchEmp = u.employee_no ? u.employee_no.toLowerCase().includes(q) : false;
      if (!matchName && !matchUser && !matchEmail && !matchEmp) return false;
    }
    if (filterRole.value && !u.roles.includes(filterRole.value)) {
      return false;
    }
    if (filterStatus.value === 'active' && !u.is_active) return false;
    if (filterStatus.value === 'suspended' && u.is_active) return false;
    if (filterStatus.value === 'must_change_pwd' && !u.must_change_password) return false;
    return true;
  });
});

async function fetchUsers() {
  loadingUsers.value = true;
  try {
    const res = await fetch('/api/v1/users');
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        users.value = data.map((u: any) => {
          let roleList: string[] = [];
          if (Array.isArray(u.role_names)) {
            roleList = u.role_names.map(String);
          } else if (Array.isArray(u.roles)) {
            roleList = u.roles.map((r: any) =>
              typeof r === 'string' ? r : (r.role_id || r.role_name || String(r))
            );
          }
          return {
            id: String(u.id),
            username: u.username || '',
            display_name: u.display_name || u.username || '使用者',
            email: u.email || '',
            is_active: u.is_active !== false,
            must_change_password: !!(u.must_change_password ?? u.is_first_login),
            active_company_id: u.active_company_id || u.primary_company_id || null,
            employee_id: u.employee_id || null,
            employee_no: u.employee_no || u.employee?.employee_no || null,
            roles: roleList,
            created_at: u.created_at || '',
          };
        });
      }
    } else {
      showToast('無法取得帳號清單', 'error');
    }
  } catch (err) {
    showToast('連線錯誤，請檢查後端服務', 'error');
  } finally {
    loadingUsers.value = false;
  }
}

function switchTab(tab: 'users' | 'roles') {
  activeTab.value = tab;
  if (tab === 'users' && users.value.length === 0 && !loadingUsers.value) {
    fetchUsers();
  }
  if (tab === 'roles' && rolesMeta.value.length === 0 && !loadingRoles.value) {
    fetchRolesMeta();
  }
}

function getRoleBadgeClass(r: string): string {
  if (typeof r !== 'string') return 'bg-slate-100 text-slate-700';
  if (r === 'ADMIN') return 'bg-rose-100 text-rose-800';
  if (r.includes('HR')) return 'bg-emerald-100 text-emerald-800';
  if (r.includes('FINANCE')) return 'bg-indigo-100 text-indigo-800';
  if (r.includes('LEGAL')) return 'bg-amber-100 text-amber-800';
  return 'bg-slate-100 text-slate-700';
}

async function fetchCompanies() {
  try {
    const res = await fetch('/api/v1/hr/companies');
    if (res.ok) {
      companies.value = await res.json();
    }
  } catch {
    // 忽略非致命錯誤
  }
}

async function fetchEmployees(companyId: string) {
  try {
    const res = await fetch(`/api/v1/hr/employees?company_id=${companyId}`);
    if (res.ok) {
      employees.value = await res.json();
    }
  } catch {
    // 忽略非致命錯誤
  }
}

// 帳號新增彈窗
const showCreateModal = ref(false);
const createForm = ref({
  username: '',
  display_name: '',
  email: '',
  password: '',
  active_company_id: props.companyId,
  employee_id: '',
  roles: ['GENERAL_USER'] as string[],
  must_change_password: true,
});

function openCreateModal() {
  const defaultComp = props.companyId || (companies.value[0]?.id ?? 'ETJ-TW');
  createForm.value = {
    username: '',
    display_name: '',
    email: '',
    password: '',
    active_company_id: defaultComp,
    employee_id: '',
    roles: ['GENERAL_USER'],
    must_change_password: true,
  };
  fetchEmployees(defaultComp);
  showCreateModal.value = true;
}

watch(
  () => createForm.value.active_company_id,
  (newComp) => {
    if (newComp && showCreateModal.value) {
      fetchEmployees(newComp);
      createForm.value.employee_id = '';
    }
  }
);

watch(
  () => createForm.value.employee_id,
  (newEmpId) => {
    if (newEmpId) {
      const targetEmp = employees.value.find((e) => e.id === newEmpId);
      if (targetEmp) {
        if (!createForm.value.display_name && targetEmp.full_name) {
          createForm.value.display_name = targetEmp.full_name;
        }
        if (!createForm.value.email && targetEmp.email) {
          createForm.value.email = targetEmp.email;
        }
      }
    }
  }
);

async function handleCreateUser() {
  if (!createForm.value.username || !createForm.value.display_name || !createForm.value.email || !createForm.value.password) {
    showToast('請填寫完整必填欄位 (帳號、姓名、Email、初始密碼)', 'error');
    return;
  }
  try {
    const targetComp = createForm.value.active_company_id || props.companyId || (companies.value[0]?.id ?? 'ETJ-TW');
    const uniqueRoles = Array.from(new Set(createForm.value.roles.filter(Boolean)));
    const payload = {
      username: createForm.value.username.trim(),
      display_name: createForm.value.display_name.trim(),
      email: createForm.value.email.trim(),
      password: createForm.value.password,
      primary_company_id: targetComp,
      active_company_id: targetComp,
      role_ids: uniqueRoles.length > 0 ? uniqueRoles : ['GENERAL_USER'],
      employee_id: createForm.value.employee_id ? createForm.value.employee_id : null,
      must_change_password: createForm.value.must_change_password,
    };
    const res = await fetch('/api/v1/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast(`帳號 ${createForm.value.username} 建立成功`);
      showCreateModal.value = false;
      await fetchUsers();
      await fetchRolesMeta();
    } else {
      const err = await res.json();
      const msg = err.error?.message || err.message || (typeof err.detail === 'string' ? err.detail : (Array.isArray(err.detail) ? err.detail.map((d: any) => d.msg).join('; ') : '建立帳號失敗'));
      showToast(msg, 'error');
    }
  } catch {
    showToast('連線異常，請稍後再試', 'error');
  }
}

// 帳號編輯彈窗
const showEditModal = ref(false);
const editUser = ref<UserItem | null>(null);
const editForm = ref({
  display_name: '',
  email: '',
  active_company_id: '',
  employee_id: '',
  must_change_password: false,
});

function openEditModal(user: UserItem) {
  editUser.value = user;
  editForm.value = {
    display_name: user.display_name,
    email: user.email,
    active_company_id: user.active_company_id || '',
    employee_id: user.employee_id || '',
    must_change_password: user.must_change_password,
  };
  showEditModal.value = true;
}

async function handleUpdateUser() {
  if (!editUser.value) return;
  try {
    const payload = {
      ...editForm.value,
      primary_company_id: editForm.value.active_company_id || null,
      employee_id: editForm.value.employee_id ? editForm.value.employee_id : null,
    };
    const res = await fetch(`/api/v1/users/${editUser.value.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast('使用者資料更新成功');
      showEditModal.value = false;
      await fetchUsers();
    } else {
      const err = await res.json();
      showToast(err.detail || '更新失敗', 'error');
    }
  } catch {
    showToast('連線異常', 'error');
  }
}

// 指派角色彈窗
const showAssignRolesModal = ref(false);
const roleAssignUser = ref<UserItem | null>(null);
const roleAssignCompany = ref<string>('');
const selectedUserRoles = ref<string[]>([]);

function openAssignRolesModal(user: UserItem) {
  roleAssignUser.value = user;
  roleAssignCompany.value = user.active_company_id || props.companyId || (companies.value[0]?.id ?? 'ETJ-TW');
  selectedUserRoles.value = [...user.roles];
  showAssignRolesModal.value = true;
}

async function handleSaveUserRoles() {
  if (!roleAssignUser.value) return;
  try {
    const targetCompany = roleAssignCompany.value || roleAssignUser.value.active_company_id || props.companyId || 'ETJ-TW';
    const payload = {
      company_id: targetCompany,
      role_ids: selectedUserRoles.value,
      role_names: selectedUserRoles.value,
    };
    const res = await fetch(`/api/v1/users/${roleAssignUser.value.id}/roles`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast(`已更新 ${roleAssignUser.value.display_name} 的角色指派`);
      showAssignRolesModal.value = false;
      await fetchUsers();
      await fetchRolesMeta();
    } else {
      const err = await res.json();
      const msg = typeof err.detail === 'string' ? err.detail : (Array.isArray(err.detail) ? err.detail.map((d: any) => d.msg).join('; ') : '角色指派失敗');
      showToast(msg, 'error');
    }
  } catch {
    showToast('連線異常', 'error');
  }
}

// 重設密碼彈窗
const showResetPwdModal = ref(false);
const resetPwdUser = ref<UserItem | null>(null);
const resetPwdForm = ref({
  new_password: '',
  must_change_password: true,
});

function openResetPwdModal(user: UserItem) {
  resetPwdUser.value = user;
  resetPwdForm.value = {
    new_password: '',
    must_change_password: true,
  };
  showResetPwdModal.value = true;
}

async function handleResetPassword() {
  if (!resetPwdUser.value) return;
  if (!resetPwdForm.value.new_password || resetPwdForm.value.new_password.length < 8) {
    showToast('新密碼長度須至少為 8 碼', 'error');
    return;
  }
  try {
    const res = await fetch(`/api/v1/users/${resetPwdUser.value.id}/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(resetPwdForm.value),
    });
    if (res.ok) {
      showToast(`已成功為 ${resetPwdUser.value.username} 重設密碼`);
      showResetPwdModal.value = false;
      await fetchUsers();
    } else {
      const err = await res.json();
      showToast(err.detail || '重設密碼失敗', 'error');
    }
  } catch {
    showToast('連線異常', 'error');
  }
}

// 啟用/停用帳號
async function toggleUserStatus(user: UserItem) {
  const isActivating = !user.is_active;
  const actionName = isActivating ? '啟用' : '停用';
  const endpoint = isActivating ? 'activate' : 'suspend';
  
  if (!isActivating && !confirm(`確定要停用帳號「${user.display_name} (${user.username})」嗎？\n停用後該使用者所有連線 sessions 將被立即撤銷強制登出。`)) {
    return;
  }

  try {
    const res = await fetch(`/api/v1/users/${user.id}/${endpoint}`, {
      method: 'POST',
    });
    if (res.ok) {
      showToast(`帳號已${actionName}`);
      await fetchUsers();
    } else {
      const err = await res.json();
      showToast(err.detail || `${actionName}失敗`, 'error');
    }
  } catch {
    showToast('連線異常', 'error');
  }
}

// ----------------------------------------------------
// Tab 2: 角色與 RBAC 權限設定相關 State 與邏輯
// ----------------------------------------------------
const rolesMeta = ref<RoleMeta[]>([]);
const permissionGroups = ref<PermissionGroup[]>([]);
const selectedRole = ref<RoleMeta | null>(null);
const selectedRolePermissions = ref<string[]>([]);

async function fetchRolesMeta() {
  loadingRoles.value = true;
  try {
    const res = await fetch('/api/v1/users/meta/roles');
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data)) {
        rolesMeta.value = data.map((r: any) => {
          const permCodes: string[] = Array.isArray(r.permission_codes) ? r.permission_codes : [];
          return {
            id: String(r.id),
            name: r.name || r.id,
            description: r.description || '',
            is_system: !!(r.is_system ?? r.is_system_builtin),
            permissions_count: r.permissions_count ?? permCodes.length,
            users_count: r.users_count ?? r.user_count ?? 0,
            permission_codes: permCodes,
          };
        });
        if (!selectedRole.value && rolesMeta.value.length > 0) {
          selectRole(rolesMeta.value[0]);
        } else if (selectedRole.value) {
          const found = rolesMeta.value.find((r) => r.id === selectedRole.value?.id);
          if (found) selectedRole.value = found;
        }
      }
    }
  } catch {
    showToast('載入角色清單失敗', 'error');
  } finally {
    loadingRoles.value = false;
  }
}

async function fetchPermissionsDictionary() {
  try {
    const res = await fetch('/api/v1/users/meta/permissions');
    if (res.ok) {
      const data = await res.json();
      const rawList = Array.isArray(data) ? data : (data.groups || []);
      permissionGroups.value = rawList.map((g: any) => ({
        module: g.module || 'OTHER',
        name: g.module_name || g.name || g.module || '其它模組',
        permissions: Array.isArray(g.permissions) ? g.permissions : [],
      }));
    }
  } catch {
    showToast('載入權限矩陣字典失敗', 'error');
  }
}

async function selectRole(role: RoleMeta) {
  selectedRole.value = role;
  if (Array.isArray((role as any).permission_codes)) {
    selectedRolePermissions.value = [...(role as any).permission_codes];
  }
  await fetchRolePermissions(role.id);
}

async function fetchRolePermissions(roleId: string) {
  try {
    const res = await fetch(`/api/v1/users/meta/roles/${roleId}/permissions`);
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.permission_codes)) {
        selectedRolePermissions.value = data.permission_codes;
      }
    }
  } catch {
    // 保持既有已載入之 permission_codes
  }
}

function isPermissionSelected(code: string): boolean {
  return selectedRolePermissions.value.includes(code);
}

function togglePermission(code: string) {
  const index = selectedRolePermissions.value.indexOf(code);
  if (index >= 0) {
    selectedRolePermissions.value.splice(index, 1);
  } else {
    selectedRolePermissions.value.push(code);
  }
}

function isGroupAllSelected(group: PermissionGroup): boolean {
  return group.permissions.every((p) => selectedRolePermissions.value.includes(p.code));
}

function toggleGroupPermissions(group: PermissionGroup) {
  const allSelected = isGroupAllSelected(group);
  if (allSelected) {
    // 取消全選
    const codes = new Set(group.permissions.map((p) => p.code));
    selectedRolePermissions.value = selectedRolePermissions.value.filter((c) => !codes.has(c));
  } else {
    // 全選
    const current = new Set(selectedRolePermissions.value);
    group.permissions.forEach((p) => current.add(p.code));
    selectedRolePermissions.value = Array.from(current);
  }
}

async function saveRolePermissions() {
  if (!selectedRole.value) return;
  savingRolePermissions.value = true;
  try {
    const res = await fetch(`/api/v1/users/meta/roles/${selectedRole.value.id}/permissions`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ permission_codes: selectedRolePermissions.value }),
    });
    if (res.ok) {
      showToast(`角色「${selectedRole.value.name}」的權限設定已成功儲存！`);
      await fetchRolesMeta();
    } else {
      const err = await res.json();
      showToast(err.detail || '儲存權限矩陣失敗', 'error');
    }
  } catch {
    showToast('連線異常，儲存失敗', 'error');
  } finally {
    savingRolePermissions.value = false;
  }
}

// 新增自訂角色彈窗
const showCreateRoleModal = ref(false);
const createRoleForm = ref({
  name: '',
  description: '',
});

async function handleCreateRole() {
  if (!createRoleForm.value.name) {
    showToast('請輸入角色代碼/名稱', 'error');
    return;
  }
  try {
    const res = await fetch('/api/v1/users/meta/roles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(createRoleForm.value),
    });
    if (res.ok) {
      showToast(`角色 ${createRoleForm.value.name} 建立成功`);
      showCreateRoleModal.value = false;
      await fetchRolesMeta();
    } else {
      const err = await res.json();
      showToast(err.detail || '建立角色失敗', 'error');
    }
  } catch {
    showToast('連線異常', 'error');
  }
}

// 刪除自訂角色
async function handleDeleteRole(role: RoleMeta) {
  if (role.is_system) {
    showToast('系統內建標準角色不可刪除', 'error');
    return;
  }
  if (!confirm(`確定要刪除自訂角色「${role.name}」嗎？\n此操作無法復原。`)) {
    return;
  }
  try {
    const res = await fetch(`/api/v1/users/meta/roles/${role.id}`, {
      method: 'DELETE',
    });
    if (res.ok) {
      showToast(`角色 ${role.name} 已刪除`);
      selectedRole.value = null;
      await fetchRolesMeta();
    } else {
      const err = await res.json();
      showToast(err.detail || '刪除失敗', 'error');
    }
  } catch {
    showToast('連線異常', 'error');
  }
}

watch(
  () => props.companyId,
  (newVal) => {
    if (newVal) {
      fetchEmployees(newVal);
    }
  },
  { immediate: true }
);

onMounted(async () => {
  await Promise.all([
    fetchUsers(),
    fetchCompanies(),
    fetchRolesMeta(),
    fetchPermissionsDictionary(),
  ]);
});
</script>

<template>
  <div class="space-y-6">
    <!-- Toast 通知條 -->
    <div
      v-if="toastMessage"
      class="fixed top-5 right-5 z-50 flex items-center px-4 py-3 rounded-xl shadow-lg border text-sm transition-all animate-bounce"
      :class="
        toastMessage.type === 'success'
          ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
          : 'bg-rose-50 border-rose-300 text-rose-800'
      "
    >
      <span class="mr-2 text-base">{{ toastMessage.type === 'success' ? '✅' : '⚠️' }}</span>
      <span>{{ toastMessage.text }}</span>
      <button @click="toastMessage = null" class="ml-4 text-slate-400 hover:text-slate-700">✕</button>
    </div>

    <!-- 頂部頁籤切換選單 -->
    <div v-if="canManageUsers || canManageRoles" class="flex items-center justify-between border-b border-border-main pb-3">
      <div class="flex items-center space-x-2">
        <button
          v-if="canManageUsers"
          @click="switchTab('users')"
          class="flex items-center px-4 py-2.5 rounded-lg text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'users'
              ? 'bg-(--color-primary) text-white shadow-xs'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          "
        >
          <span class="mr-2 text-base">👥</span>
          <span>{{ t('usersView.tabs.users') }}</span>
          <span
            class="ml-2 px-2 py-0.5 text-xs rounded-full"
            :class="activeTab === 'users' ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-700'"
          >
            {{ totalUsersCount }}
          </span>
        </button>

        <button
          v-if="canManageRoles"
          @click="switchTab('roles')"
          class="flex items-center px-4 py-2.5 rounded-lg text-sm font-semibold transition cursor-pointer"
          :class="
            activeTab === 'roles'
              ? 'bg-(--color-primary) text-white shadow-xs'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          "
        >
          <span class="mr-2 text-base">🛡️</span>
          <span>{{ t('usersView.tabs.roles') }}</span>
          <span
            class="ml-2 px-2 py-0.5 text-xs rounded-full"
            :class="activeTab === 'roles' ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-700'"
          >
            {{ rolesMeta.length }}
          </span>
        </button>
      </div>

      <div class="text-xs text-text-muted flex items-center space-x-2">
        <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        <span>企業級身分認證與存取控制 (IAM & RBAC)</span>
      </div>
    </div>

    <!-- ======================================================== -->
    <!-- Tab 1: 帳號名冊與管理 (Users View)                       -->
    <!-- ======================================================== -->
    <div v-if="canManageUsers && activeTab === 'users'" class="space-y-6">
      <!-- 統計指標卡片群 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex items-center space-x-3.5">
          <div class="w-11 h-11 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-xl font-bold">
            👤
          </div>
          <div>
            <div class="text-xs font-medium text-text-muted">總使用者帳號</div>
            <div class="text-xl font-bold text-slate-800">{{ totalUsersCount }}</div>
          </div>
        </div>

        <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex items-center space-x-3.5">
          <div class="w-11 h-11 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl font-bold">
            ✅
          </div>
          <div>
            <div class="text-xs font-medium text-text-muted">正常啟用帳號</div>
            <div class="text-xl font-bold text-emerald-700">{{ activeUsersCount }}</div>
          </div>
        </div>

        <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex items-center space-x-3.5">
          <div class="w-11 h-11 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center text-xl font-bold">
            🚫
          </div>
          <div>
            <div class="text-xs font-medium text-text-muted">已停用 / 凍結</div>
            <div class="text-xl font-bold text-rose-700">{{ suspendedUsersCount }}</div>
          </div>
        </div>

        <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex items-center space-x-3.5">
          <div class="w-11 h-11 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center text-xl font-bold">
            🔑
          </div>
          <div>
            <div class="text-xs font-medium text-text-muted">待首次登入改密碼</div>
            <div class="text-xl font-bold text-amber-700">{{ mustChangePwdCount }}</div>
          </div>
        </div>
      </div>

      <!-- 搜尋與過濾工具列 -->
      <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2.5 flex-1 min-w-70">
          <!-- 關鍵字搜尋 -->
          <div class="relative flex-1 min-w-50">
            <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">🔍</span>
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜尋帳號、姓名、Email、員工工號..."
              class="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 transition"
            />
          </div>

          <!-- 角色過濾 -->
          <select
            v-model="filterRole"
            class="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-hidden cursor-pointer"
          >
            <option value="">全部角色 (All Roles)</option>
            <option v-for="r in rolesMeta" :key="r.name" :value="r.name">{{ r.name }}</option>
          </select>

          <!-- 狀態過濾 -->
          <select
            v-model="filterStatus"
            class="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-hidden cursor-pointer"
          >
            <option value="">全部狀態</option>
            <option value="active">正常啟用</option>
            <option value="suspended">已停用</option>
            <option value="must_change_pwd">待變更密碼</option>
          </select>

          <button
            @click="fetchUsers"
            class="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition"
            title="重新整理"
          >
            🔄
          </button>
        </div>

        <div>
          <button
            @click="openCreateModal"
            class="px-3.5 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs transition flex items-center space-x-1.5 cursor-pointer"
          >
            <span>+</span>
            <span>{{ t('usersView.createUser') }}</span>
          </button>
        </div>
      </div>

      <!-- 帳號資料表格 -->
      <div class="bg-white rounded-xl border border-border-main shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="bg-slate-50/80 border-b border-border-main text-text-muted font-semibold uppercase tracking-wider">
                <th class="py-3 px-4">{{ t('usersView.table.username') }}</th>
                <th class="py-3 px-4">{{ t('usersView.table.email') }}</th>
                <th class="py-3 px-4">{{ t('usersView.table.activeCompany') }}</th>
                <th class="py-3 px-4">{{ t('hr.employeeDetailModal.employeeId') }}</th>
                <th class="py-3 px-4">{{ t('usersView.table.roles') }}</th>
                <th class="py-3 px-4 text-center">{{ t('usersView.table.accountStatus') }}</th>
                <th class="py-3 px-4 text-right">{{ t('usersView.table.actions') }}</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border-main">
              <tr v-if="loadingUsers" class="hover:bg-slate-50">
                <td colspan="7" class="py-8 text-center text-slate-400">
                  <span class="inline-block animate-spin mr-2">⏳</span>
                  正在載入使用者帳號資料...
                </td>
              </tr>
              <tr v-else-if="filteredUsers.length === 0" class="hover:bg-slate-50">
                <td colspan="7" class="py-8 text-center text-slate-400">
                  查無符合條件之帳號資料
                </td>
              </tr>
              <tr
                v-else
                v-for="u in filteredUsers"
                :key="u.id"
                class="hover:bg-slate-50/60 transition"
              >
                <!-- 使用者名稱與姓名 -->
                <td class="py-3 px-4">
                  <div class="flex items-center space-x-2.5">
                    <div
                      class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shadow-xs"
                      :class="u.is_active ? 'bg-blue-600 text-white' : 'bg-slate-300 text-slate-600'"
                    >
                      {{ u.display_name ? u.display_name[0] : 'U' }}
                    </div>
                    <div>
                      <div class="font-semibold text-slate-800 flex items-center space-x-1.5">
                        <span>{{ u.display_name }}</span>
                        <span
                          v-if="u.must_change_password"
                          class="px-1.5 py-0.2 bg-amber-50 text-amber-700 text-[10px] rounded border border-amber-200"
                          title="首次登入須變更密碼"
                        >
                          需改密
                        </span>
                      </div>
                      <div class="text-[11px] text-slate-400 font-mono">@{{ u.username }}</div>
                    </div>
                  </div>
                </td>

                <!-- Email -->
                <td class="py-3 px-4 text-slate-700 font-mono text-[11px]">
                  {{ u.email }}
                </td>

                <!-- 主屬公司 -->
                <td class="py-3 px-4">
                  <span class="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px] font-mono">
                    {{ u.active_company_id || '未設定' }}
                  </span>
                </td>

                <!-- 關聯員工 -->
                <td class="py-3 px-4">
                  <span v-if="u.employee_no" class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-[11px] font-mono font-medium">
                    🪪 {{ u.employee_no }}
                  </span>
                  <span v-else class="text-slate-400 text-[11px]">未綁定</span>
                </td>

                <!-- 角色清單 -->
                <td class="py-3 px-4">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="r in u.roles"
                      :key="r"
                      class="px-2 py-0.5 rounded text-[10px] font-medium"
                      :class="getRoleBadgeClass(r)"
                    >
                      {{ r }}
                    </span>
                  </div>
                </td>

                <!-- 啟用狀態 -->
                <td class="py-3 px-4 text-center">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                    :class="
                      u.is_active
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-rose-50 text-rose-700 border border-rose-200'
                    "
                  >
                    <span class="w-1.5 h-1.5 rounded-full mr-1.5" :class="u.is_active ? 'bg-emerald-500' : 'bg-rose-500'"></span>
                    {{ u.is_active ? '啟用' : '停用' }}
                  </span>
                </td>

                <!-- 操作管理群 -->
                <td class="py-3 px-4 text-right">
                  <div class="inline-flex items-center space-x-1.5">
                    <button
                      @click="openEditModal(u)"
                      class="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded transition cursor-pointer"
                      title="編輯帳號資料"
                    >
                      ✏️
                    </button>
                    <button
                      @click="openAssignRolesModal(u)"
                      class="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded transition cursor-pointer"
                      title="分配角色權限"
                    >
                      🛡️
                    </button>
                    <button
                      @click="openResetPwdModal(u)"
                      class="p-1.5 text-slate-500 hover:text-amber-600 hover:bg-amber-50 rounded transition cursor-pointer"
                      title="管理員重設密碼"
                    >
                      🔑
                    </button>
                    <button
                      @click="toggleUserStatus(u)"
                      class="p-1.5 rounded transition cursor-pointer"
                      :class="
                        u.is_active
                          ? 'text-slate-400 hover:text-rose-600 hover:bg-rose-50'
                          : 'text-emerald-600 hover:bg-emerald-50'
                      "
                      :title="u.is_active ? '停用帳號' : '啟用帳號'"
                    >
                      {{ u.is_active ? '🚫' : '✅' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ======================================================== -->
    <!-- Tab 2: 角色與 RBAC 權限設定 (Roles & Permissions Matrix) -->
    <!-- ======================================================== -->
    <div v-else-if="canManageRoles && activeTab === 'roles'" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <!-- 左側：角色清單側欄 (佔 4 欄) -->
        <div class="lg:col-span-4 space-y-4">
          <div class="bg-white p-4 rounded-xl border border-border-main shadow-xs flex items-center justify-between">
            <h3 class="text-sm font-bold text-slate-800 flex items-center space-x-2">
              <span>🛡️</span>
              <span>系統角色名冊</span>
            </h3>
            <button
              @click="showCreateRoleModal = true"
              class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 transition cursor-pointer"
            >
              + 自訂角色
            </button>
          </div>

          <!-- 角色卡片列表 -->
          <div class="space-y-2">
            <div
              v-for="r in rolesMeta"
              :key="r.id"
              @click="selectRole(r)"
              class="bg-white p-3.5 rounded-xl border transition-all cursor-pointer shadow-xs"
              :class="
                selectedRole?.id === r.id
                  ? 'border-blue-500 ring-2 ring-blue-500/10 bg-blue-50/20'
                  : 'border-border-main hover:border-slate-300'
              "
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2">
                  <span class="font-bold text-xs text-slate-800 font-mono">{{ r.name }}</span>
                  <span
                    v-if="r.is_system"
                    class="px-1.5 py-0.2 bg-slate-100 text-slate-600 text-[10px] rounded font-medium"
                  >
                    內建
                  </span>
                  <span
                    v-else
                    class="px-1.5 py-0.2 bg-purple-100 text-purple-700 text-[10px] rounded font-medium"
                  >
                    自訂
                  </span>
                </div>
                <div class="text-[11px] text-slate-500">
                  👥 {{ r.users_count }} 位成員
                </div>
              </div>

              <p class="text-[11px] text-slate-500 mt-1 line-clamp-1">
                {{ r.description || '無描述' }}
              </p>

              <div class="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span>授權項目：<strong class="text-slate-700">{{ r.permissions_count }}</strong> 項</span>
                <button
                  v-if="!r.is_system"
                  @click.stop="handleDeleteRole(r)"
                  class="text-rose-500 hover:text-rose-700 text-[11px] cursor-pointer"
                >
                  刪除角色
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 右側：權限矩陣配置主面板 (佔 8 欄) -->
        <div class="lg:col-span-8 space-y-4">
          <div v-if="selectedRole" class="bg-white p-5 rounded-xl border border-border-main shadow-xs space-y-5">
            <!-- 標題與操作按鈕 -->
            <div class="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-border-main">
              <div>
                <div class="flex items-center space-x-2">
                  <h3 class="text-base font-bold text-slate-800 font-mono">{{ selectedRole.name }}</h3>
                  <span
                    class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="selectedRole.is_system ? 'bg-slate-100 text-slate-700' : 'bg-purple-100 text-purple-700'"
                  >
                    {{ selectedRole.is_system ? '系統內建核心角色' : '企業自訂擴充角色' }}
                  </span>
                </div>
                <p class="text-xs text-text-muted mt-1">{{ selectedRole.description }}</p>
              </div>

              <div class="flex items-center space-x-2">
                <button
                  @click="saveRolePermissions"
                  :disabled="savingRolePermissions"
                  class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs transition flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  <span v-if="savingRolePermissions" class="animate-spin mr-1">⏳</span>
                  <span>💾 儲存權限矩陣配置</span>
                </button>
              </div>
            </div>

            <!-- 矩陣權限分組展開與勾選 -->
            <div class="space-y-4">
              <div
                v-for="grp in permissionGroups"
                :key="grp.module"
                class="border border-slate-200 rounded-xl overflow-hidden bg-slate-50/40"
              >
                <!-- 分組標頭 -->
                <div class="px-4 py-2.5 bg-slate-100/80 border-b border-slate-200 flex items-center justify-between">
                  <div class="flex items-center space-x-2">
                    <span class="text-xs font-bold text-slate-800 uppercase tracking-wider font-mono">
                      {{ grp.name }} ({{ grp.module }})
                    </span>
                    <span class="text-[11px] text-slate-400">
                      — 共 {{ grp.permissions.length }} 項權限
                    </span>
                  </div>

                  <button
                    @click="toggleGroupPermissions(grp)"
                    class="text-xs text-blue-600 hover:text-blue-800 font-medium cursor-pointer"
                  >
                    {{ isGroupAllSelected(grp) ? '取消全選' : '本組全選' }}
                  </button>
                </div>

                <!-- 權限列表 -->
                <div class="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <label
                    v-for="p in grp.permissions"
                    :key="p.code"
                    class="flex items-start space-x-2.5 p-2 rounded-lg border transition cursor-pointer"
                    :class="
                      isPermissionSelected(p.code)
                        ? 'bg-blue-50/60 border-blue-200 text-slate-800'
                        : 'bg-white border-slate-200/80 text-slate-600 hover:border-slate-300'
                    "
                  >
                    <input
                      type="checkbox"
                      :checked="isPermissionSelected(p.code)"
                      @change="togglePermission(p.code)"
                      class="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                    <div class="min-w-0">
                      <div class="text-xs font-semibold leading-tight">
                        {{ p.name }}
                      </div>
                      <div class="text-[10px] text-slate-400 font-mono mt-0.5 truncate">
                        {{ p.code }}
                      </div>
                      <div class="text-[11px] text-slate-500 mt-1 line-clamp-1">
                        {{ p.description }}
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="bg-white p-12 rounded-xl border border-border-main text-center text-slate-400">
            請由左側點選角色以檢視並配置其授權矩陣
          </div>
        </div>
      </div>
    </div>

    <!-- 若完全無權限時展示之面板 -->
    <div v-else class="bg-white p-12 rounded-xl border border-slate-200 text-center space-y-2">
      <div class="text-3xl">🔒</div>
      <div class="text-sm font-bold text-slate-800">無帳號與權限管理權限</div>
      <div class="text-xs text-slate-500">您的帳號未被授權系統使用者管理或 RBAC 角色矩陣維護權限。</div>
    </div>

    <!-- ======================================================== -->
    <!-- 彈窗群 (Modals)                                          -->
    <!-- ======================================================== -->

    <!-- 1. 新增使用者帳號彈窗 -->
    <div
      v-if="showCreateModal"
      class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden animate-fade-in">
        <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <h3 class="font-bold text-sm text-slate-800 flex items-center space-x-2">
            <span>👤</span>
            <span>建立新系統帳號</span>
          </h3>
          <button @click="showCreateModal = false" class="text-slate-400 hover:text-slate-700">✕</button>
        </div>

        <div class="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1">使用者登入帳號 (Username) <span class="text-rose-500">*</span></label>
            <input
              v-model="createForm.username"
              type="text"
              placeholder="例如: john.doe"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 font-mono"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block font-semibold text-slate-700 mb-1">顯示姓名 (Display Name) <span class="text-rose-500">*</span></label>
              <input
                v-model="createForm.display_name"
                type="text"
                placeholder="例如: 王小明"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block font-semibold text-slate-700 mb-1">電子郵件 (Email) <span class="text-rose-500">*</span></label>
              <input
                v-model="createForm.email"
                type="email"
                placeholder="例如: john.doe@etron.com"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 font-mono"
              />
            </div>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">初始登入密碼 <span class="text-rose-500">*</span></label>
            <input
              v-model="createForm.password"
              type="password"
              placeholder="至少 8 碼"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 font-mono"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block font-semibold text-slate-700 mb-1">主屬營運公司</label>
              <select
                v-model="createForm.active_company_id"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden cursor-pointer"
              >
                <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }} ({{ c.id }})</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold text-slate-700 mb-1">關聯員工工號 (可選)</label>
              <select
                v-model="createForm.employee_id"
                class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden cursor-pointer"
              >
                <option value="">無 (外部或系統專用帳號)</option>
                <option v-for="e in employees" :key="e.id" :value="e.id">
                  {{ e.employee_no }} - {{ e.full_name || `${e.last_name || ''}${e.first_name || ''}` }}
                </option>
              </select>
            </div>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">指派初始角色 (可複選)</label>
            <div class="grid grid-cols-2 gap-2 p-2 bg-slate-50 rounded-lg border border-slate-200 max-h-36 overflow-y-auto">
              <label
                v-for="r in rolesMeta"
                :key="r.name"
                class="flex items-center space-x-2 text-slate-700 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :value="r.name"
                  v-model="createForm.roles"
                  class="rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <span class="font-mono text-xs">{{ r.name }}</span>
              </label>
            </div>
          </div>

          <div class="p-3 bg-amber-50 rounded-lg border border-amber-200 flex items-center space-x-2">
            <input
              type="checkbox"
              id="create_must_change"
              v-model="createForm.must_change_password"
              class="rounded text-amber-600 focus:ring-amber-500 cursor-pointer"
            />
            <label for="create_must_change" class="text-amber-800 font-medium cursor-pointer">
              強制使用者於首次登入時必須變更密碼 (推薦啟用)
            </label>
          </div>
        </div>

        <div class="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end space-x-2">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
          >
            取消
          </button>
          <button
            @click="handleCreateUser"
            class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs cursor-pointer"
          >
            建立帳號
          </button>
        </div>
      </div>
    </div>

    <!-- 2. 編輯帳號彈窗 -->
    <div
      v-if="showEditModal"
      class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-fade-in">
        <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <h3 class="font-bold text-sm text-slate-800 flex items-center space-x-2">
            <span>✏️</span>
            <span>編輯帳號資料 ({{ editUser?.username }})</span>
          </h3>
          <button @click="showEditModal = false" class="text-slate-400 hover:text-slate-700">✕</button>
        </div>

        <div class="p-6 space-y-4 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1">顯示姓名</label>
            <input
              v-model="editForm.display_name"
              type="text"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">電子郵件 (Email)</label>
            <input
              v-model="editForm.email"
              type="email"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 font-mono"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">主屬公司</label>
            <select
              v-model="editForm.active_company_id"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden cursor-pointer"
            >
              <option value="">未指定</option>
              <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }} ({{ c.id }})</option>
            </select>
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">關聯員工</label>
            <select
              v-model="editForm.employee_id"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden cursor-pointer"
            >
              <option value="">無 (未綁定)</option>
              <option v-for="e in employees" :key="e.id" :value="e.id">
                {{ e.employee_no }} - {{ e.full_name || `${e.last_name || ''}${e.first_name || ''}` }}
              </option>
            </select>
          </div>

          <div class="flex items-center space-x-2 pt-2">
            <input
              type="checkbox"
              id="edit_must_change"
              v-model="editForm.must_change_password"
              class="rounded text-amber-600 focus:ring-amber-500 cursor-pointer"
            />
            <label for="edit_must_change" class="text-slate-700 cursor-pointer">
              標記為需變更密碼 (下次登入強制跳出修改彈窗)
            </label>
          </div>
        </div>

        <div class="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end space-x-2">
          <button
            @click="showEditModal = false"
            class="px-4 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
          >
            取消
          </button>
          <button
            @click="handleUpdateUser"
            class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs cursor-pointer"
          >
            儲存變更
          </button>
        </div>
      </div>
    </div>

    <!-- 3. 指派使用者角色彈窗 -->
    <div
      v-if="showAssignRolesModal"
      class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-fade-in">
        <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <h3 class="font-bold text-sm text-slate-800 flex items-center space-x-2">
            <span>🛡️</span>
            <span>指派角色 — {{ roleAssignUser?.display_name }}</span>
          </h3>
          <button @click="showAssignRolesModal = false" class="text-slate-400 hover:text-slate-700">✕</button>
        </div>

        <div class="p-6 space-y-3 text-xs">
          <!-- 生效公司選擇 -->
          <div>
            <label class="block font-semibold text-slate-700 mb-1">角色生效公司範圍 (Company Scope) <span class="text-rose-500">*</span></label>
            <select
              v-model="roleAssignCompany"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden cursor-pointer"
            >
              <option v-for="c in companies" :key="c.id" :value="c.id">{{ c.name }} ({{ c.id }})</option>
            </select>
          </div>

          <p class="text-slate-500 mb-1 pt-1 font-medium">
            勾選該帳號所擁有的系統角色，權限將依勾選項目聯集生效：
          </p>

          <div class="space-y-2 max-h-60 overflow-y-auto">
            <label
              v-for="r in rolesMeta"
              :key="r.id"
              class="flex items-start space-x-3 p-2.5 rounded-lg border transition cursor-pointer"
              :class="
                selectedUserRoles.includes(r.id)
                  ? 'bg-blue-50/60 border-blue-300 text-slate-800 shadow-xs'
                  : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
              "
            >
              <input
                type="checkbox"
                :value="r.id"
                v-model="selectedUserRoles"
                class="mt-0.5 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <div class="min-w-0 flex-1">
                <div class="font-bold text-xs font-mono flex items-center space-x-1.5">
                  <span class="text-blue-700">{{ r.id }}</span>
                  <span class="text-slate-700 font-sans font-medium text-xs">({{ r.name }})</span>
                  <span v-if="r.is_system" class="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200 font-sans">內建</span>
                </div>
                <div class="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{{ r.description }}</div>
              </div>
            </label>
          </div>
        </div>

        <div class="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end space-x-2">
          <button
            @click="showAssignRolesModal = false"
            class="px-4 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
          >
            取消
          </button>
          <button
            @click="handleSaveUserRoles"
            class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs cursor-pointer"
          >
            確定指派
          </button>
        </div>
      </div>
    </div>

    <!-- 4. 重設密碼彈窗 -->
    <div
      v-if="showResetPwdModal"
      class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-sm overflow-hidden animate-fade-in">
        <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <h3 class="font-bold text-sm text-slate-800 flex items-center space-x-2">
            <span>🔑</span>
            <span>管理員重設密碼</span>
          </h3>
          <button @click="showResetPwdModal = false" class="text-slate-400 hover:text-slate-700">✕</button>
        </div>

        <div class="p-6 space-y-4 text-xs">
          <div class="p-3 bg-amber-50 rounded-lg border border-amber-200 text-amber-800 leading-relaxed">
            您即將重設 <strong>{{ resetPwdUser?.display_name }} (@{{ resetPwdUser?.username }})</strong> 的登入密碼。
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">輸入新臨時密碼 (至少8碼)</label>
            <input
              v-model="resetPwdForm.new_password"
              type="password"
              placeholder="••••••••"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 font-mono"
            />
          </div>

          <div class="flex items-center space-x-2 pt-1">
            <input
              type="checkbox"
              id="reset_must_change"
              v-model="resetPwdForm.must_change_password"
              class="rounded text-amber-600 focus:ring-amber-500 cursor-pointer"
            />
            <label for="reset_must_change" class="text-slate-700 cursor-pointer font-medium">
              強制使用者登入後立即變更密碼
            </label>
          </div>
        </div>

        <div class="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end space-x-2">
          <button
            @click="showResetPwdModal = false"
            class="px-4 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
          >
            取消
          </button>
          <button
            @click="handleResetPassword"
            class="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow-xs cursor-pointer"
          >
            確認重設
          </button>
        </div>
      </div>
    </div>

    <!-- 5. 新增自訂角色彈窗 -->
    <div
      v-if="showCreateRoleModal"
      class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-fade-in">
        <div class="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <h3 class="font-bold text-sm text-slate-800 flex items-center space-x-2">
            <span>🛡️</span>
            <span>新增自訂系統角色</span>
          </h3>
          <button @click="showCreateRoleModal = false" class="text-slate-400 hover:text-slate-700">✕</button>
        </div>

        <div class="p-6 space-y-4 text-xs">
          <div>
            <label class="block font-semibold text-slate-700 mb-1">角色代碼 / 名稱 <span class="text-rose-500">*</span></label>
            <input
              v-model="createRoleForm.name"
              type="text"
              placeholder="例如: AUDIT_SPECIALIST"
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500 font-mono uppercase"
            />
          </div>

          <div>
            <label class="block font-semibold text-slate-700 mb-1">角色業務說明描述</label>
            <textarea
              v-model="createRoleForm.description"
              rows="3"
              placeholder="請詳細說明該角色的職能定位與權限範圍..."
              class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:border-blue-500"
            ></textarea>
          </div>
        </div>

        <div class="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end space-x-2">
          <button
            @click="showCreateRoleModal = false"
            class="px-4 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 text-xs font-semibold cursor-pointer"
          >
            取消
          </button>
          <button
            @click="handleCreateRole"
            class="px-4 py-2 rounded-lg bg-(--color-primary) hover:bg-primary-hover text-white text-xs font-semibold shadow-xs cursor-pointer"
          >
            建立角色
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

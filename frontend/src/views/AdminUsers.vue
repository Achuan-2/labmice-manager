<template>
  <div class="admin-users-page">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4">
      <div class="text-base font-bold text-gray-800">系统名称设置</div>
      <div class="text-xs text-gray-500 mt-1 mb-4">
        可设置完整的系统名称，登录页、侧栏和浏览器标题会自动同步
      </div>
      <el-form v-if="authStore.isAdmin" inline @submit.prevent="saveSystemName">
        <el-form-item label="系统名称" class="mb-0">
          <el-input
            v-model="systemName"
            maxlength="64"
            show-word-limit
            placeholder="请输入完整的系统名称"
            style="width: 320px; max-width: 100%"
            @keyup.enter="saveSystemName"
          />
        </el-form-item>
        <el-form-item class="mb-0">
          <el-button type="primary" :loading="savingSettings" @click="saveSystemName">保存名称</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">用户账号设置</div>
        <div class="text-xs text-gray-500 mt-1">
          管理员可新增管理员或普通用户，分别设置独立账号与密码；普通用户可查看数据、提交转鼠申请
        </div>
      </div>

      <div class="flex items-center gap-2">
        <el-button v-if="authStore.isAdmin" type="success" @click="openAddDialog('guest')">新增普通用户</el-button>
        <el-button v-if="authStore.isAdmin" type="primary" @click="openAddDialog('admin')">
          <el-icon class="mr-1"><Plus /></el-icon> 新增管理员
        </el-button>
      </div>
    </div>

    <!-- Non-admin warning -->
    <div v-if="!authStore.isAdmin" class="bg-white p-12 text-center rounded-xl border border-gray-200">
      <div class="text-3xl mb-3">🔒</div>
      <div class="text-base font-bold text-gray-800 mb-1">当前处于游客访问模式</div>
      <div class="text-xs text-gray-500 mb-4">管理员账号管理需要登录后方可操作</div>
      <el-button type="primary" @click="showLoginModal = true">立即登录管理员</el-button>
    </div>

    <!-- Admin list table -->
    <div v-else class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table v-loading="loading" :data="admins" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" align="center" />

        <el-table-column prop="display_name" label="显示姓名 / 身份" min-width="160">
          <template #default="{ row }">
            <span class="font-bold text-gray-800">{{ row.display_name || row.username }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="username" label="用户账号" width="160">
          <template #default="{ row }">
            <span class="font-mono text-gray-700">{{ row.username }}</span>
            <el-tag v-if="row.username === authStore.user.username" size="small" type="success" class="ml-2">
              当前账号
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="role" label="权限角色" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="primary">{{ row.role === 'admin' ? '系统管理员' : '普通用户' }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" min-width="180">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center gap-1">
              <el-button size="small" type="primary" link @click="openNameDialog(row)">
                修改名称
              </el-button>
              <el-button size="small" type="primary" link @click="openPasswordDialog(row)">
                修改密码
              </el-button>

              <el-popconfirm
                :title="`确定删除账号 [${row.username}] 吗？`"
                @confirm="handleDeleteAdmin(row.id)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    type="danger"
                    link
                    :disabled="row.id === authStore.user.id || (row.role === 'admin' && admins.filter(user => user.role === 'admin').length <= 1)"
                  >
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Add Admin Dialog -->
    <el-dialog v-model="showAddDialog" :title="addForm.role === 'admin' ? '添加管理员' : '添加普通用户'" width="420px">
      <el-form :model="addForm" ref="addFormRef" :rules="addRules" label-width="80px">
        <el-form-item label="显示姓名" prop="display_name">
          <el-input v-model="addForm.display_name" placeholder="如 张三、管家A" />
        </el-form-item>
        <el-form-item label="账号" prop="username">
          <el-input v-model="addForm.username" placeholder="英文/数字字母账号" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="addForm.password" type="password" show-password placeholder="设置登录密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitAddAdmin">创建账号</el-button>
      </template>
    </el-dialog>

    <!-- Update Display Name Dialog -->
    <el-dialog v-model="showNameDialog" :title="`修改用户 [${currentAdmin?.username}] 名称`" width="400px">
      <el-form :model="nameForm" label-width="80px" @submit.prevent="submitUpdateName">
        <el-form-item label="用户名称" required>
          <el-input
            v-model="nameForm.display_name"
            maxlength="64"
            show-word-limit
            placeholder="请输入用户名称"
            @keyup.enter="submitUpdateName"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNameDialog = false">取消</el-button>
        <el-button type="primary" :loading="updatingName" @click="submitUpdateName">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- Update Password Dialog -->
    <el-dialog v-model="showPasswordDialog" :title="`修改账号 [${currentAdmin?.username}] 密码`" width="400px">
      <el-form :model="passwordForm" label-width="80px">
        <el-form-item label="新密码" required>
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="submitUpdatePassword">确认修改</el-button>
      </template>
    </el-dialog>

    <LoginDialog v-model="showLoginModal" @login-success="loadAdmins" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import LoginDialog from '@/components/LoginDialog.vue'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const systemName = ref(settingsStore.systemName)
const savingSettings = ref(false)
watch(() => settingsStore.systemName, value => {
  if (!savingSettings.value) systemName.value = value
})

const loading = ref(false)
const admins = ref([])
const showLoginModal = ref(false)

const showAddDialog = ref(false)
const creating = ref(false)
const addFormRef = ref(null)
const addForm = reactive({
  role: 'guest',
  display_name: '',
  username: '',
  password: ''
})

const addRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }]
}

const showPasswordDialog = ref(false)
const currentAdmin = ref(null)
const showNameDialog = ref(false)
const updatingName = ref(false)
const nameForm = reactive({
  display_name: ''
})
const passwordForm = reactive({
  new_password: ''
})

function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN', { hour12: false })
}

async function loadAdmins() {
  if (!authStore.isAdmin) return
  loading.value = true
  try {
    admins.value = await authApi.listAdmins()
  } catch (e) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function saveSystemName() {
  const cleanName = systemName.value.trim()
  if (!cleanName) {
    ElMessage.warning('系统名称不能为空')
    return
  }
  savingSettings.value = true
  try {
    await settingsStore.update(cleanName)
    systemName.value = settingsStore.systemName
    ElMessage.success('系统名称已更新')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '系统名称保存失败')
  } finally {
    savingSettings.value = false
  }
}

function openAddDialog(role = 'guest') {
  Object.assign(addForm, { display_name: '', username: '', password: '', role })
  showAddDialog.value = true
}

async function submitAddAdmin() {
  if (!addFormRef.value || creating.value) return
  await addFormRef.value.validate(async (valid) => {
    if (!valid || creating.value) return
    creating.value = true
    try {
      await authApi.createAdmin(addForm)
      ElMessage.success('账号添加成功')
      showAddDialog.value = false
      loadAdmins()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '创建失败')
    } finally {
      creating.value = false
    }
  })
}

function openPasswordDialog(admin) {
  currentAdmin.value = admin
  passwordForm.new_password = ''
  showPasswordDialog.value = true
}

function openNameDialog(admin) {
  currentAdmin.value = admin
  nameForm.display_name = admin.display_name || admin.username
  showNameDialog.value = true
}

async function submitUpdateName() {
  const displayName = nameForm.display_name.trim()
  if (!displayName) {
    ElMessage.warning('用户名称不能为空')
    return
  }
  if (!currentAdmin.value || updatingName.value) return

  updatingName.value = true
  try {
    await authApi.updateAdminDisplayName(currentAdmin.value.id, { display_name: displayName })
    if (currentAdmin.value.id === authStore.user.id) {
      await authStore.fetchMe()
    }
    await loadAdmins()
    showNameDialog.value = false
    ElMessage.success('用户名称已更新')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '用户名称修改失败')
  } finally {
    updatingName.value = false
  }
}

async function submitUpdatePassword() {
  if (!passwordForm.new_password.trim()) {
    ElMessage.warning('请输入新密码')
    return
  }
  try {
    await authApi.updateAdminPassword(currentAdmin.value.id, passwordForm)
    ElMessage.success('密码修改成功')
    showPasswordDialog.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  }
}

async function handleDeleteAdmin(id) {
  try {
    await authApi.deleteAdmin(id)
    ElMessage.success('账号已删除')
    loadAdmins()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => {
  systemName.value = settingsStore.systemName
  loadAdmins()
})
</script>

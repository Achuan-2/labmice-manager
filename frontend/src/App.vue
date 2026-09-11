<template>
  <!-- If not logged in, display the login screen -->
  <LoginView v-if="!authStore.isAuthenticated" />

  <!-- If authenticated (either admin or guest), show the system -->
  <div v-else class="app-container">
    <!-- Sidebar -->
    <aside v-if="!isMobile" class="app-sidebar">
      <div class="p-4 border-b border-gray-800 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow">
          🐁
        </div>
        <div>
          <div class="font-bold text-white text-base leading-tight">{{ settingsStore.groupName }}小鼠管理</div>
        </div>
      </div>

      <!-- Navigation Menu -->
      <div class="py-3 flex-1 flex flex-col gap-1 px-2 overflow-y-auto">
        <router-link
          v-for="item in visibleNavItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ 'active': isCurrent(item.path) }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span class="flex-1">{{ item.label }}</span>
          <span v-if="item.path === '/todos' && todoCount" class="todo-count">{{ todoCount > 99 ? '99+' : todoCount }}</span>
        </router-link>
      </div>
    </aside>

    <el-drawer v-if="isMobile" v-model="sidebarOpen" direction="ltr" size="min(280px, 85vw)" title="导航菜单" class="mobile-navigation">
      <nav aria-label="主导航">
        <router-link v-for="item in visibleNavItems" :key="item.path" :to="item.path"
          class="nav-link" :class="{ active: isCurrent(item.path) }" @click="sidebarOpen = false">
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <span v-if="item.path === '/todos' && todoCount" class="todo-count">{{ todoCount > 99 ? '99+' : todoCount }}</span>
        </router-link>
      </nav>
    </el-drawer>

    <!-- Main Section -->
    <div class="app-main">
      <!-- Top Header -->
      <header class="app-header">
        <div class="flex items-center gap-2">
          <button v-if="isMobile" class="menu-toggle" type="button" aria-label="打开导航菜单"
            :aria-expanded="sidebarOpen" @click="sidebarOpen = true">
            <el-icon><Menu /></el-icon>
          </button>
          <div class="text-lg font-semibold text-gray-800">{{ currentTitle }}</div>
        </div>

        <div class="flex items-center gap-3">
          <!-- Auth Badge -->
          <div v-if="authStore.isAdmin" class="flex items-center gap-2">
            <el-tag type="success" effect="plain" class="font-medium">
              <el-icon class="mr-1"><UserFilled /></el-icon>
              管理员: {{ authStore.user.display_name || authStore.user.username }}
            </el-tag>
            <el-button size="small" type="danger" plain @click="authStore.logout">退出登录</el-button>
          </div>

          <div v-else class="flex items-center gap-2">
            <el-tag type="info" effect="plain">
              <el-icon class="mr-1"><User /></el-icon>
              访客: {{ authStore.user.display_name || authStore.user.username }}
            </el-tag>
            <el-button size="small" type="primary" plain @click="authStore.logout">
              切换管理员
            </el-button>
          </div>
        </div>
      </header>

      <!-- Router Content -->
      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { todosApi } from '@/api'
import LoginView from '@/components/LoginView.vue'
import { ElNotification } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const todoCount = ref(0)
const mobileQuery = window.matchMedia('(max-width: 767px)')
const isMobile = ref(mobileQuery.matches)
const sidebarOpen = ref(false)
function updateViewport(event) {
  isMobile.value = event.matches
  sidebarOpen.value = false
}
watch(() => route.fullPath, () => { sidebarOpen.value = false })
watch(() => authStore.isAuthenticated, () => { sidebarOpen.value = false })
async function refreshTodoNotifications() {
  if (!authStore.isAuthenticated || !authStore.isAdmin) {
    todoCount.value = 0
    return
  }
  try {
    const todos = await todosApi.listTodos({ bucket: 'today' })
    todoCount.value = todos.length
    const notifiedKey = `mouse_lab_notified_todos_${authStore.user?.id || authStore.user?.username || 'user'}`
    let notifiedIds = []
    try {
      notifiedIds = JSON.parse(sessionStorage.getItem(notifiedKey) || '[]')
    } catch {
      sessionStorage.removeItem(notifiedKey)
    }
    const notified = new Set(Array.isArray(notifiedIds) ? notifiedIds : [])
    const automatic = todos.filter(todo => todo.source !== 'manual' && !notified.has(todo.id))
    if (automatic.length) {
      ElNotification({
        title: '待办自动提醒',
        message: `有 ${automatic.length} 条笼位提醒需要处理，点击查看。`,
        type: 'warning',
        duration: 8000,
        onClick: () => router.push('/todos'),
      })
      for (const todo of automatic) notified.add(todo.id)
      sessionStorage.setItem(notifiedKey, JSON.stringify([...notified]))
    }
  } catch {
    todoCount.value = 0
  }
}
watch(() => [authStore.isAuthenticated, authStore.isAdmin], ([authenticated, isAdmin]) => {
  if (authenticated && isAdmin) refreshTodoNotifications()
  else todoCount.value = 0
}, { immediate: true })

const navItems = [
  { path: '/', label: '总览看板', icon: 'DataAnalysis' },
  { path: '/mice', label: '小鼠列表', icon: 'List' },
  { path: '/cages', label: '笼位管理', icon: 'Grid' },
  { path: '/todos', label: '待办提醒', icon: 'Bell', adminOnly: true },
  { path: '/transfer-requests', label: '转鼠需求及反馈', icon: 'Tickets' },
  { path: '/genotypes', label: '基因鉴定结果', icon: 'Aim' },
  { path: '/members', label: '课题组成员', icon: 'User' },
  { path: '/transfers', label: '领用与流转日志', icon: 'Sort' },
  { path: '/import-export', label: '数据导入导出', icon: 'Document' },
  { path: '/admins', label: '管理员设置', icon: 'Setting', adminOnly: true },
]

const visibleNavItems = computed(() => {
  return navItems
    .filter(item => !item.adminOnly || authStore.isAdmin)
    .map(item => {
      if (item.path === '/import-export' && !authStore.isAdmin) {
        return { ...item, label: '数据导出' }
      }
      return item
    })
})

const currentTitle = computed(() => {
  if (route.path === '/import-export' && !authStore.isAdmin) {
    return '数据导出'
  }
  return route.meta?.title || settingsStore.systemName
})

function isCurrent(path) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

let todoRefreshTimer = null
function handleUnauthorized() {
  authStore.logout()
}
const handleTodosUpdated = () => {
  if (authStore.isAdmin) refreshTodoNotifications()
}
onMounted(() => {
  settingsStore.load()
  mobileQuery.addEventListener('change', updateViewport)
  authStore.fetchMe()
  window.addEventListener('auth-unauthorized', handleUnauthorized)
  window.addEventListener('todos-updated', handleTodosUpdated)
  todoRefreshTimer = window.setInterval(() => {
    if (authStore.isAdmin) refreshTodoNotifications()
  }, 5 * 60 * 1000)
})
onUnmounted(() => {
  mobileQuery.removeEventListener('change', updateViewport)
  window.removeEventListener('auth-unauthorized', handleUnauthorized)
  window.removeEventListener('todos-updated', handleTodosUpdated)
  if (todoRefreshTimer) window.clearInterval(todoRefreshTimer)
})
</script>

<style scoped>
.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  color: #94a3b8;
  text-decoration: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.nav-link:hover {
  background-color: #1e293b;
  color: #f8fafc;
}

.nav-link.active {
  background-color: #2563eb;
  color: #ffffff;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3);
}

.nav-icon {
  font-size: 16px;
}
.todo-count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #ef4444;
  color: white;
  font-size: 11px;
  line-height: 20px;
  text-align: center;
  font-weight: 700;
}
.menu-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  color: #334155;
  font-size: 22px;
  cursor: pointer;
}
</style>

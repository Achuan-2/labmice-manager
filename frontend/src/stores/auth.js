import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'
import { ElMessage } from 'element-plus'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('mouse_lab_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('mouse_lab_user') || 'null'))

  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => isAuthenticated.value && user.value?.role === 'admin')
  const isGuest = computed(() => isAuthenticated.value && user.value?.role === 'guest')

  async function fetchMe() {
    if (!token.value) {
      user.value = null
      return
    }
    try {
      const data = await authApi.getMe()
      if (data && data.is_authenticated) {
        user.value = data
        localStorage.setItem('mouse_lab_user', JSON.stringify(data))
      } else {
        logout()
      }
    } catch (e) {
      logout()
    }
  }

  async function login(username, password) {
    try {
      const res = await authApi.login({ username: username.trim(), password: password.trim() })
      token.value = res.access_token
      user.value = { ...res.user, is_authenticated: true }
      localStorage.setItem('mouse_lab_token', res.access_token)
      localStorage.setItem('mouse_lab_user', JSON.stringify(user.value))
      ElMessage.success(`登录成功，欢迎 ${res.user.display_name || res.user.username}`)
      return true
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '账号或密码错误，请核对后重试')
      return false
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('mouse_lab_token')
    localStorage.removeItem('mouse_lab_user')
  }

  return {
    token,
    user,
    isAuthenticated,
    isAdmin,
    isGuest,
    fetchMe,
    login,
    logout
  }
})

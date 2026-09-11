<template>
  <el-dialog
    v-model="visible"
    title="管理员登录"
    width="420px"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="mb-4 text-sm text-gray-500">
      管理员登录后可进行小鼠分配、录入编辑、换笼、Excel导入等操作。游客可免登录直接浏览全站数据。
    </div>

    <el-form :model="form" ref="formRef" :rules="rules" label-width="70px">
      <el-form-item label="账号" prop="username">
        <el-input v-model="form.username" placeholder="请输入管理员账号" prefix-icon="User" />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
            placeholder="请输入管理员密码"
          show-password
          prefix-icon="Lock"
          @keyup.enter="handleLogin"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-between items-center">
        <el-button size="small" @click="useGuest">游客只读浏览</el-button>
        <div class="flex gap-2">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="handleLogin">登录</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue', 'login-success'])

const authStore = useAuthStore()
const visible = ref(false)
const loading = ref(false)
const formRef = ref(null)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入管理员账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入管理员密码', trigger: 'blur' }]
}

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function useGuest() {
  authStore.logout()
  visible.value = false
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    const ok = await authStore.login(form.username, form.password)
    loading.value = false
    if (ok) {
      visible.value = false
      emit('login-success')
    }
  })
}
</script>

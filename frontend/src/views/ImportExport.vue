<template>
  <div class="import-export-page">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-6 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">{{ authStore.isAdmin ? '数据导入与导出中心' : '数据导出中心' }}</div>
        <div class="text-xs text-gray-500 mt-1">
          {{ authStore.isAdmin ? '支持上传实验室新 Excel 表格追加导入，支持单文件或多文件批量上传，以及系统全量数据导出备份' : '支持系统全量小鼠档案与鼠房笼位明细数据导出备份' }}
        </div>
      </div>
    </div>

    <!-- Import Result Feedback (if available) -->
    <div v-if="lastImportResult && authStore.isAdmin" class="bg-white p-5 rounded-xl shadow-sm border border-green-200 mb-6 transition">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="text-green-600 text-lg">✅</span>
          <span class="font-bold text-gray-800 text-base">最近导入反馈</span>
          <el-tag size="small" type="success" effect="plain" class="font-semibold">
            {{ lastImportResult.message }}
          </el-tag>
        </div>
        <el-button link size="small" type="info" @click="lastImportResult = null">关闭反馈</el-button>
      </div>

      <!-- Quick Metrics Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 mb-3">
        <div class="bg-gray-50 p-2.5 rounded-lg border border-gray-100 text-center">
          <div class="text-xs text-gray-400 font-medium">小鼠追加/更新</div>
          <div class="text-lg font-bold text-blue-600 mt-0.5">
            {{ lastImportResult.details?.mice_imported || 0 }} <span class="text-xs font-normal text-gray-500">只</span>
          </div>
        </div>
        <div class="bg-gray-50 p-2.5 rounded-lg border border-gray-100 text-center">
          <div class="text-xs text-gray-400 font-medium">笼位同步</div>
          <div class="text-lg font-bold text-green-600 mt-0.5">
            {{ lastImportResult.details?.cages_imported || 0 }} <span class="text-xs font-normal text-gray-500">个</span>
          </div>
        </div>
        <div class="bg-gray-50 p-2.5 rounded-lg border border-gray-100 text-center">
          <div class="text-xs text-gray-400 font-medium">基因鉴定</div>
          <div class="text-lg font-bold text-purple-600 mt-0.5">
            {{ lastImportResult.details?.genotypes_imported || 0 }} <span class="text-xs font-normal text-gray-500">条</span>
          </div>
        </div>
        <div class="bg-gray-50 p-2.5 rounded-lg border border-gray-100 text-center">
          <div class="text-xs text-gray-400 font-medium">转鼠需求</div>
          <div class="text-lg font-bold text-indigo-600 mt-0.5">
            {{ lastImportResult.details?.transfer_requests_imported || 0 }} <span class="text-xs font-normal text-gray-500">条</span>
          </div>
        </div>
        <div class="bg-gray-50 p-2.5 rounded-lg border border-gray-100 text-center">
          <div class="text-xs text-gray-400 font-medium">亲本性别推断</div>
          <div class="text-lg font-bold text-amber-600 mt-0.5">
            {{ lastImportResult.details?.inferred_genders_count || 0 }} <span class="text-xs font-normal text-gray-500">个</span>
          </div>
        </div>
        <div class="bg-gray-50 p-2.5 rounded-lg border border-gray-100 text-center">
          <div class="text-xs text-gray-400 font-medium">引物记录</div>
          <div class="text-lg font-bold text-teal-600 mt-0.5">
            {{ lastImportResult.details?.primers_imported || 0 }} <span class="text-xs font-normal text-gray-500">条</span>
          </div>
        </div>
      </div>

      <!-- File breakdown if multiple files -->
      <div v-if="lastImportResult.file_summaries && lastImportResult.file_summaries.length > 1" class="mt-3">
        <div class="text-xs font-bold text-gray-600 mb-2">多文件逐一解析明细：</div>
        <div class="flex flex-col gap-1.5 max-h-40 overflow-y-auto">
          <div
            v-for="(item, idx) in lastImportResult.file_summaries"
            :key="idx"
            class="text-xs px-3 py-1.5 rounded flex items-center justify-between border"
            :class="item.success ? 'bg-emerald-50 border-emerald-100 text-emerald-800' : 'bg-red-50 border-red-100 text-red-700'"
          >
            <div class="flex items-center gap-2">
              <span>{{ item.success ? '📄' : '⚠️' }}</span>
              <span class="font-mono font-medium">{{ item.filename }}</span>
            </div>
            <div>
              <span v-if="item.success" class="font-semibold">已写入 {{ item.imported_count }} 项记录</span>
              <span v-else class="text-red-600 font-semibold">{{ item.error }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div :class="authStore.isAdmin ? 'grid grid-cols-1 md:grid-cols-2 gap-6 mb-6' : 'max-w-2xl mb-6'">
      <!-- Section 1: Upload Custom Excel -->
      <div v-if="authStore.isAdmin" class="bg-white p-5 rounded-xl shadow-sm border border-gray-200 flex flex-col justify-between">
        <div>
          <div class="flex items-center gap-2 mb-3">
            <span class="text-xl">📤</span>
            <span class="text-base font-bold text-gray-800">上传新 Excel 表格导入</span>
          </div>
          <div class="text-xs text-gray-500 leading-relaxed mb-4">
            支持拖拽上传实验室更新的 <code class="bg-gray-100 px-1 py-0.5 rounded text-blue-600 font-mono">.xlsx</code> 或 <code class="bg-gray-100 px-1 py-0.5 rounded text-blue-600 font-mono">.xls</code> 文件。支持<strong>同时选择多个文件</strong>或多次连续上传，系统将智能识别表头并追加小鼠档案、笼位芯片及基因鉴定记录。
          </div>

          <el-upload
            ref="uploadRef"
            drag
            action="#"
            :auto-upload="false"
            :show-file-list="true"
            multiple
            accept=".xlsx, .xls"
            v-model:file-list="fileList"
            :on-change="handleFileChange"
            :disabled="!authStore.isAdmin"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text text-xs">
              将 Excel 文件拖拽到此处，或 <em>点击选择文件</em>
              <div class="text-[11px] text-gray-400 mt-1">支持多选文件批量导入，可连续多次上传</div>
            </div>
            <template #tip>
              <div class="flex items-center justify-between mt-2 text-xs">
                <span class="text-gray-400">格式要求：.xlsx / .xls 文件</span>
                <span
                  v-if="fileList.length > 0"
                  class="text-blue-600 cursor-pointer hover:underline font-medium"
                  @click="clearAllFiles"
                >
                  清空待上传列表 ({{ fileList.length }})
                </span>
              </div>
            </template>
          </el-upload>
        </div>

        <div class="mt-4">
          <el-button
            type="primary"
            class="w-full"
            :loading="uploading"
            :disabled="fileList.length === 0 || !authStore.isAdmin"
            @click="submitUpload"
          >
            <el-icon class="mr-1"><UploadFilled /></el-icon>
            {{ uploading ? '正在解析导入中，请稍候...' : (fileList.length > 1 ? `开始批量解析并导入 (${fileList.length} 个文件)` : '开始解析并导入') }}
          </el-button>
          <div v-if="!authStore.isAdmin" class="text-[11px] text-amber-600 mt-2 text-center">
            * 仅管理员账号可执行数据导入操作
          </div>
          <div class="mt-4 pt-4 border-t border-gray-100">
            <input ref="databaseInput" type="file" accept=".db" style="display: none" aria-hidden="true" tabindex="-1" @change="selectDatabase" />
            <el-button
              type="warning"
              plain
              class="w-full"
              :loading="restoringDatabase"
              :disabled="!authStore.isAdmin || exportingDatabase || uploading"
              @click="databaseInput?.click()"
            >
              导入数据库并完整恢复 (.db)
            </el-button>
            <div class="text-xs text-gray-500 leading-relaxed mt-2">
              使用 .db 文件完整恢复全部数据及账号；恢复前会自动备份当前数据库。
            </div>
          </div>
        </div>
      </div>

      <!-- Section 2: Data Export -->
      <div class="bg-white p-5 rounded-xl shadow-sm border border-gray-200 flex flex-col justify-between">
        <div>
          <div class="flex items-center gap-2 mb-3">
            <span class="text-xl">💾</span>
            <span class="text-base font-bold text-gray-800">全量数据导出与备份</span>
          </div>
          <div class="text-xs text-gray-500 leading-relaxed mb-4">
            {{ authStore.isAdmin
              ? 'Excel 用于查看和汇报；导出 .db 数据库可完整备份全部数据，包括账号、领取关系、基因鉴定及流转历史，并通过导入 .db 完整恢复。'
              : '导出 Excel 文件可直接用于组会汇报、档案存档或离线备份。' }}
          </div>

          <div class="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-blue-800 space-y-1.5 mb-4">
            <div class="font-bold flex items-center gap-1">
              <span>ℹ️ 导出说明：</span>
            </div>
            <div>• 导出的表格包含小鼠完整系谱父母、实时周龄、当前笼位与分配人</div>
            <div>• 导出文件可直接用于组会汇报、档案存档或群晖 NAS 离线备份</div>
          </div>
        </div>

        <div class="export-actions flex flex-col gap-2">
          <div v-if="authStore.isAdmin" class="mb-2">
            <el-button type="primary" class="w-full" :loading="exportingDatabase" :disabled="restoringDatabase" @click="exportDatabase">
              导出完整数据库 (.db)
            </el-button>
            <div class="text-xs text-gray-500 leading-relaxed mt-1">
              仅管理员可执行数据库备份。导出的 .db 包含全部数据（含账号），最大支持 512 MB。
            </div>
          </div>
          <el-button type="primary" plain class="w-full" :loading="exportingMice" @click="exportMice">
            <el-icon class="mr-1"><Download /></el-icon>
            导出小鼠全量档案 (.xlsx)
          </el-button>
          <el-button type="success" plain class="w-full" :loading="exportingCages" @click="exportCages">
            <el-icon class="mr-1"><Download /></el-icon>
            导出鼠房笼位明细 (.xlsx)
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { importExportApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const authStore = useAuthStore()

const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)
const exportingMice = ref(false)
const exportingCages = ref(false)
const lastImportResult = ref(null)
const databaseInput = ref(null)
const exportingDatabase = ref(false)
const restoringDatabase = ref(false)

async function exportDatabase() {
  if (exportingDatabase.value || restoringDatabase.value || !authStore.isAdmin) return
  exportingDatabase.value = true
  try {
    await importExportApi.exportDatabase()
  } finally {
    exportingDatabase.value = false
  }
}

async function selectDatabase(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || restoringDatabase.value || !authStore.isAdmin) return
  if (!file.name.toLowerCase().endsWith('.db') || file.size > 512 * 1024 * 1024) {
    return ElMessage.warning('请选择不超过 512 MB 的 .db 数据库文件')
  }
  restoringDatabase.value = true
  try {
    const data = new FormData()
    data.append('file', file)
    const result = await importExportApi.restoreDatabase(data)
    authStore.logout()
    await ElMessageBox.alert(`${result.message}。恢复前备份：data/backups/${result.safety_backup}`, '恢复成功',
      { confirmButtonText: '重新登录', showClose: false, closeOnClickModal: false, closeOnPressEscape: false })
    window.location.reload()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.response?.data?.detail || '数据库恢复失败，请稍后重试')
  } finally {
    restoringDatabase.value = false
  }
}

function handleFileChange(file) {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
  if (!isExcel) {
    ElMessage.warning(`文件 ${file.name} 不是 Excel 文件，请选择 .xlsx 或 .xls 格式`)
    fileList.value = fileList.value.filter(f => f.uid !== file.uid)
  }
}

function clearAllFiles() {
  fileList.value = []
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

async function submitUpload() {
  if (!authStore.isAdmin) {
    ElMessage.error('仅管理员可执行导入操作')
    return
  }
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择要上传的 Excel 文件')
    return
  }

  uploading.value = true
  lastImportResult.value = null

  try {
    const formData = new FormData()
    fileList.value.forEach(f => {
      const actual = f.raw || f
      if (actual) {
        formData.append('files', actual, actual.name || f.name)
      }
    })

    const res = await importExportApi.uploadExcel(formData)
    ElMessage.success(res.message || '上传并解析完成！')
    lastImportResult.value = res

    // Clear file list completely so user can immediately upload more files
    clearAllFiles()
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '上传解析失败'
    ElMessage.error(msg)
  } finally {
    uploading.value = false
  }
}

async function exportMice() {
  if (exportingMice.value) return
  exportingMice.value = true
  try {
    await importExportApi.exportMice()
  } finally {
    exportingMice.value = false
  }
}

async function exportCages() {
  if (exportingCages.value) return
  exportingCages.value = true
  try {
    await importExportApi.exportCages()
  } finally {
    exportingCages.value = false
  }
}
</script>

<style scoped>
.export-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>

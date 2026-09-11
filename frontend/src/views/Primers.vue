<template>
  <div class="primers-page">
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div>
        <div class="text-base font-bold text-gray-800">引物总表与基因鉴定档案</div>
        <div class="text-xs text-gray-500 mt-1">
          课题组各品系基因型鉴定引物序列、条带大小及 JAX/NCBI 参考链接
        </div>
      </div>

      <div class="flex items-center gap-3">
        <el-input
          v-model="keyword"
          placeholder="搜索品系简称、序列或条带大小"
          clearable
          prefix-icon="Search"
          style="width: 260px"
          @keyup.enter="loadPrimers"
        />
        <el-button type="primary" @click="loadPrimers">查询</el-button>
        <el-button v-if="authStore.isAdmin" type="success" plain @click="openAddDialog">
          <el-icon class="mr-1"><Plus /></el-icon> 新增引物
        </el-button>
      </div>
    </div>

    <!-- Primers Table -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table v-loading="loading" :data="primers" stripe style="width: 100%">
        <el-table-column prop="primer_no" label="编号" width="70" align="center" />

        <el-table-column prop="strain_short" label="品系简称" width="150">
          <template #default="{ row }">
            <span class="font-bold text-blue-700">{{ row.strain_short }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="strain_full" label="品系全称" min-width="180">
          <template #default="{ row }">
            <span class="text-xs text-gray-600 font-mono">{{ row.strain_full || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="sequence" label="引物序列 (5' → 3')" min-width="220">
          <template #default="{ row }">
            <div class="flex items-center justify-between">
              <span class="font-mono text-xs text-emerald-700 font-bold select-all">{{ row.sequence || '-' }}</span>
              <el-button
                v-if="row.sequence"
                size="small"
                link
                type="primary"
                @click="copySequence(row.sequence)"
              >
                复制
              </el-button>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="band_size" label="片段大小 / 产物" min-width="160">
          <template #default="{ row }">
            <div class="text-xs text-gray-700 whitespace-pre-line">{{ row.band_size || '-' }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="source" label="来源 / 基因类型" width="130">
          <template #default="{ row }">
            <div class="text-xs text-gray-500">
              <div>{{ row.source || '' }}</div>
              <el-tag v-if="row.gene_type" size="small" type="info">{{ row.gene_type }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="url" label="官方链接" width="100">
          <template #default="{ row }">
            <a
              v-if="row.url"
              :href="row.url"
              target="_blank"
              class="text-xs text-blue-600 hover:underline flex items-center gap-1"
            >
              JAX/主页 ↗
            </a>
            <span v-else class="text-xs text-gray-300">-</span>
          </template>
        </el-table-column>

        <el-table-column v-if="authStore.isAdmin" label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="info" link @click="openEditDialog(row)">编辑</el-button>
            <el-popconfirm title="确定删除该引物记录吗？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Add/Edit Primer Dialog -->
    <el-dialog v-model="showPrimerDialog" :title="isEdit ? '编辑引物' : '新增引物'" width="520px">
      <el-form :model="primerForm" label-width="90px">
        <el-form-item label="品系简称" required>
          <el-input v-model="primerForm.strain_short" placeholder="如 5xFAD, Trap2" />
        </el-form-item>
        <el-form-item label="品系全称">
          <el-input v-model="primerForm.strain_full" placeholder="官方完整品系名称" />
        </el-form-item>
        <el-form-item label="引物序列">
          <el-input v-model="primerForm.sequence" placeholder="5'->3' 碱基序列" />
        </el-form-item>
        <el-form-item label="片段大小">
          <el-input v-model="primerForm.band_size" type="textarea" :rows="2" placeholder="如 Mutant=129bp, WT=216bp" />
        </el-form-item>
        <el-form-item label="来源/编号">
          <el-input v-model="primerForm.source" placeholder="如 JAX:034848" />
        </el-form-item>
        <el-form-item label="参考网址">
          <el-input v-model="primerForm.url" placeholder="https://www.jax.org/strain/..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPrimerDialog = false">取消</el-button>
        <el-button type="primary" @click="submitPrimerForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { primersApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const loading = ref(false)
const primers = ref([])
const keyword = ref('')

const showPrimerDialog = ref(false)
const isEdit = ref(false)
const currentEditId = ref(null)

const primerForm = reactive({
  strain_short: '',
  strain_full: '',
  sequence: '',
  band_size: '',
  source: '',
  url: ''
})

async function loadPrimers() {
  loading.value = true
  try {
    const params = { keyword: keyword.value || undefined }
    primers.value = await primersApi.listPrimers(params)
  } catch (e) {
    ElMessage.error('加载引物档案失败')
  } finally {
    loading.value = false
  }
}

function copySequence(seq) {
  navigator.clipboard.writeText(seq)
  ElMessage.success('引物序列已复制到剪贴板')
}

function openAddDialog() {
  isEdit.value = false
  currentEditId.value = null
  Object.assign(primerForm, {
    strain_short: '',
    strain_full: '',
    sequence: '',
    band_size: '',
    source: '',
    url: ''
  })
  showPrimerDialog.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  currentEditId.value = row.id
  Object.assign(primerForm, {
    strain_short: row.strain_short,
    strain_full: row.strain_full || '',
    sequence: row.sequence || '',
    band_size: row.band_size || '',
    source: row.source || '',
    url: row.url || ''
  })
  showPrimerDialog.value = true
}

async function submitPrimerForm() {
  if (!primerForm.strain_short.trim()) {
    ElMessage.warning('请输入品系简称')
    return
  }
  try {
    if (isEdit.value) {
      await primersApi.updatePrimer(currentEditId.value, primerForm)
      ElMessage.success('引物已更新')
    } else {
      await primersApi.createPrimer(primerForm)
      ElMessage.success('引物已添加')
    }
    showPrimerDialog.value = false
    loadPrimers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function handleDelete(id) {
  try {
    await primersApi.deletePrimer(id)
    ElMessage.success('引物已删除')
    loadPrimers()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadPrimers()
})
</script>

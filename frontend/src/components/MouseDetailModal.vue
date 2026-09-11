<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="720px"
    destroy-on-close
    class="mouse-detail-modal"
  >
    <div v-loading="loading" class="mouse-detail-body">
      <!-- Pedigree History Navigation Breadcrumb -->
      <div
        v-if="navHistory.length > 0"
        class="mb-3 flex items-center justify-between bg-purple-50/90 border border-purple-200 rounded-lg px-3 py-1.5 text-xs text-purple-900 shadow-2xs"
      >
        <div class="flex items-center gap-1.5 flex-wrap">
          <span class="font-bold flex items-center gap-1">🧬 系谱溯源:</span>
          <template v-for="(item, idx) in navHistory" :key="idx">
            <span
              class="font-mono text-purple-700 cursor-pointer hover:underline hover:text-purple-900 font-semibold"
              @click="goToHistory(idx)"
              :title="`返回查看 ${item.code}`"
            >
              {{ item.code }}
            </span>
            <span class="text-gray-400 text-[10px]">→</span>
          </template>
          <span class="font-mono font-bold text-purple-950 bg-purple-200/60 px-1.5 py-0.5 rounded">
            {{ mouse?.mouse_code }}
          </span>
        </div>
        <el-button size="small" type="primary" link @click="goBack">
          ← 返回上一代 ({{ navHistory[navHistory.length - 1].code }})
        </el-button>
      </div>

      <template v-if="mouse">
        <!-- EDIT FORM MODE -->
        <div v-if="isEditing" class="p-1">
          <div class="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 text-xs text-blue-900 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base">✏️</span>
              <span class="font-bold">直接编辑小鼠档案 [{{ mouse.mouse_code }}]</span>
            </div>
            <span class="text-blue-600 text-[11px]">保存后将即刻同步更新全系统档案、笼位及流转信息</span>
          </div>

          <el-form :model="editForm" label-width="100px" size="default">
            <div class="grid grid-cols-2 gap-x-4 gap-y-1">
              <el-form-item label="耳标编号" required>
                <el-input v-model="editForm.mouse_code" :disabled="!mouse.id" placeholder="如 E962" />
              </el-form-item>

              <el-form-item label="小鼠品系" required>
                <el-select
                  v-model="editForm.strain"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="选择或直接输入品系"
                  style="width: 100%"
                >
                  <el-option
                    v-for="s in editStrainOptions"
                    :key="s"
                    :label="s"
                    :value="s"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="小鼠性别">
                <el-radio-group v-model="editForm.gender">
                  <el-radio-button value="M">♂ 雄 (M)</el-radio-button>
                  <el-radio-button value="F">♀ 雌 (F)</el-radio-button>
                  <el-radio-button value="未知">未知</el-radio-button>
                </el-radio-group>
              </el-form-item>

              <el-form-item label="当前状态">
                <el-select
                  v-model="editForm.status"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="选择或输入新状态"
                  style="width: 100%"
                >
                  <el-option
                    v-for="st in ALL_STATUSES"
                    :key="st.value"
                    :label="st.label"
                    :value="st.value"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="出生日期" class="self-start">
                <el-date-picker
                  v-model="editForm.dob"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="YYYY-MM-DD"
                  style="width: 100%"
                />
              </el-form-item>

              <el-form-item label="父母系谱">
                <el-input
                  v-model="editForm.parents"
                  placeholder="如 E925M+E822F"
                  clearable
                />
              </el-form-item>

              <el-form-item label="主基因型">
                <el-select
                  v-model="editForm.genotype_1"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="阳性/阴性/HET/WT"
                  style="width: 100%"
                  clearable
                >
                  <el-option label="阳性" value="阳性" />
                  <el-option label="阴性" value="阴性" />
                  <el-option label="杂合子 (HET)" value="杂合子" />
                  <el-option label="纯合子 (HO)" value="纯合子" />
                  <el-option label="野生型 (WT)" value="野生型" />
                </el-select>
              </el-form-item>

              <el-form-item label="次基因型">
                <el-input v-model="editForm.genotype_2" placeholder="可选输入次要鉴定结果" />
              </el-form-item>

              <el-form-item label="所在鼠房">
                <el-select
                  v-model="editForm.source_room"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="如 东四105, 枫林"
                  style="width: 100%"
                  clearable
                >
                  <el-option v-for="r in editRoomOptions" :key="r" :label="r" :value="r" />
                </el-select>
              </el-form-item>

              <el-form-item label="所在笼位">
                <el-input v-model="editForm.cage_code" placeholder="如 7A, 05-1H" />
              </el-form-item>

              <el-form-item label="当前领取人">
                <el-select
                  v-model="editForm.owner_name"
                  filterable
                  clearable
                  allow-create
                  placeholder="可选指定领取人"
                  style="width: 100%"
                >
                  <el-option
                    v-for="c in editClaimerOptions"
                    :key="c.name"
                    :label="c.name"
                    :value="c.name"
                  >
                    <div class="flex items-center justify-between">
                      <span class="flex items-center gap-1.5">
                        <span
                          class="w-2.5 h-2.5 rounded-full inline-block shadow-2xs"
                          :style="{ backgroundColor: c.color || '#2563eb' }"
                        ></span>
                        <span class="font-bold">{{ c.name }}</span>
                        <span class="text-xs text-gray-400">({{ c.role || '学生' }})</span>
                      </span>
                      <span class="text-xs text-gray-400">已领 {{ c.mouse_count || 0 }} 只</span>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>

              <el-form-item label="领用日期">
                <el-date-picker
                  v-model="editForm.claim_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="YYYY-MM-DD"
                  style="width: 100%"
                />
              </el-form-item>

              <el-form-item label="领用用途" class="col-span-2">
                <el-input v-model="editForm.claim_purpose" placeholder="如: 行为学实验、膜片钳记录等" />
              </el-form-item>

              <el-form-item label="档案备注" class="col-span-2">
                <el-input
                  v-model="editForm.notes"
                  type="textarea"
                  :rows="2"
                  placeholder="记录该小鼠的其他重要信息或操作历史"
                />
              </el-form-item>
            </div>
          </el-form>
        </div>

        <!-- VIEW MODE -->
        <div v-else>
          <!-- Top Status Banner -->
          <div class="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4 mb-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center text-2xl shadow-sm">
                🐁
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-xl font-bold font-mono text-gray-900">{{ mouse.mouse_code }}</span>
                  <el-tag :type="getStatusType(mouse.status)" size="small" effect="dark">
                    {{ mouseStatusLabel(mouse) }}
                  </el-tag>
                  <el-tag
                    v-if="mouse.gender === 'M'"
                    size="small"
                    type="primary"
                    effect="light"
                    class="font-bold"
                  >
                    ♂ 雄 (M)
                  </el-tag>
                  <el-tag
                    v-else-if="mouse.gender === 'F'"
                    size="small"
                    type="danger"
                    effect="light"
                    class="font-bold"
                  >
                    ♀ 雌 (F)
                  </el-tag>
                  <el-tag v-else size="small" type="info">性别未知</el-tag>
                </div>
                <div class="text-xs text-gray-500 mt-1 flex items-center gap-2">
                  <span>品系: <b class="text-blue-700 font-semibold">{{ mouse.strain || '未记录' }}</b></span>
                  <span v-if="isClaimedOutOfCage(mouse)">· 笼位: <b class="text-orange-600">出笼</b></span>
                  <span v-if="mouse.cage_room">· 鼠房: <b class="text-gray-700">{{ mouse.cage_room }}</b></span>
                  <span v-if="mouse.cage_code">· 笼号: <el-button v-if="mouse.cage_id" type="primary" link @click="openCageDetail">{{ mouse.cage_code }}</el-button><b v-else class="font-mono text-orange-600">{{ mouse.cage_code }}</b></span>
                </div>
              </div>
            </div>

            <div v-if="mouse.owner_name" class="text-right">
              <div class="text-xs text-gray-400">当前领取人</div>
              <div class="mt-0.5">
                <span
                  class="text-xs font-bold px-2.5 py-1 rounded border inline-flex items-center gap-1"
                  :style="getClaimerTagStyle(mouse.owner_name)"
                >
                  👤 {{ mouse.owner_name }}
                </span>
              </div>
            </div>
          </div>

          <!-- Section 1: Basic Info & Pedigree (父母系谱) -->
          <div class="grid grid-cols-2 gap-3 mb-4 text-xs">
            <!-- 父母系谱 Highlight Card -->
            <div class="col-span-2 bg-purple-50/80 border border-purple-200 rounded-xl p-3.5 flex items-start justify-between">
              <div>
                <div class="text-purple-800 font-bold flex items-center gap-1.5 mb-1.5">
                  <span>🧬 父母系谱 (Parents)</span>
                </div>
                <div class="font-mono text-sm text-purple-900 font-bold">
                  {{ mouse.parents || '暂无系谱记录 / 未填写' }}
                </div>
              </div>
              <div v-if="parsedParents.length > 0" class="flex flex-wrap gap-1.5 max-w-[320px] justify-end">
                <span
                  v-for="p in parsedParents"
                  :key="p.code"
                  class="px-2.5 py-1 rounded-full text-xs font-mono font-bold shadow-2xs cursor-pointer transition-all hover:scale-105 active:scale-95 select-none flex items-center gap-1"
                  :class="p.gender === 'M' ? 'bg-blue-100 text-blue-800 border border-blue-300 hover:bg-blue-200' : (p.gender === 'F' ? 'bg-pink-100 text-pink-800 border border-pink-300 hover:bg-pink-200' : 'bg-purple-100 text-purple-800 border border-purple-300 hover:bg-purple-200')"
                  :title="`点击穿透查看${p.gender === 'M' ? '父本 ♂' : (p.gender === 'F' ? '母本 ♀' : '亲本')} [${p.code}] 的完整档案与系谱`"
                  @click="navigateToParent(p.code)"
                >
                  <span>{{ p.gender === 'M' ? '父本 ♂' : (p.gender === 'F' ? '母本 ♀' : '亲本') }} {{ p.code }}</span>
                </span>
              </div>
            </div>

            <!-- Basic Info Item -->
            <div class="bg-gray-50 border border-gray-200/70 rounded-xl p-3 space-y-2">
              <div class="flex justify-between">
                <span class="text-gray-500">出生日期 (DOB):</span>
                <span class="font-mono font-bold text-gray-800">{{ mouse.dob || '-' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">当前周龄 / 日龄:</span>
                <span v-if="mouse.age_weeks !== null" class="font-bold text-emerald-600">
                  {{ mouse.age_weeks }} 周 ({{ mouse.age_days }} 天)
                </span>
                <span v-else class="text-gray-400">-</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">所在位置:</span>
                <span class="text-gray-800 font-medium">
                  {{ mouse.cage_room || '未入室' }} <el-button v-if="mouse.cage_id" type="primary" link @click="openCageDetail">[{{ mouse.cage_code }}]</el-button><span v-else-if="mouse.cage_code" class="font-mono text-orange-600">[{{ mouse.cage_code }}]</span><span v-else-if="isClaimedOutOfCage(mouse)" class="text-orange-600">（出笼）</span>
                </span>
              </div>
            </div>

            <!-- Claimer & Purpose -->
            <div class="bg-gray-50 border border-gray-200/70 rounded-xl p-3 space-y-2">
              <div class="flex justify-between items-center">
                <span class="text-gray-500">领取人 / 责任人:</span>
                <span
                  v-if="mouse.owner_name"
                  class="font-bold px-2 py-0.5 rounded text-xs border"
                  :style="getClaimerTagStyle(mouse.owner_name)"
                >
                  👤 {{ mouse.owner_name }}
                </span>
                <span v-else class="text-gray-400 font-bold">未分配</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">领用日期:</span>
                <span class="font-mono text-gray-700">{{ mouse.claim_date || '-' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">领用用途:</span>
                <span class="text-gray-800 truncate max-w-[150px]" :title="mouse.claim_purpose">{{ mouse.claim_purpose || '-' }}</span>
              </div>
            </div>
          </div>

          <!-- Remarks / Notes -->
          <div v-if="mouse.notes" class="bg-amber-50/50 border border-amber-200/60 rounded-xl p-2.5 text-xs text-amber-900 mb-4 flex items-start gap-2">
            <span>📝</span>
            <div class="leading-relaxed">
              <span class="font-bold">档案备注: </span>{{ mouse.notes }}
            </div>
          </div>

          <!-- Section 2: Genotype Tests (PCR 鉴定记录) -->
          <div class="mb-4">
            <div class="flex items-center justify-between mb-2">
              <div class="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                <span>🔬 PCR 基因型鉴定记录</span>
                <el-badge :value="mouse.genotypes?.length || (mouse.genotype_1 ? 1 : 0)" type="primary" class="ml-1" />
              </div>
              <div v-if="mouse.genotype_1" class="text-xs">
                主鉴定结果:
                <el-tag size="small" type="success" effect="plain" class="font-bold ml-1">
                  {{ mouse.genotype_1 }}
                </el-tag>
                <el-tag v-if="mouse.genotype_2" size="small" type="warning" effect="plain" class="ml-1">
                  {{ mouse.genotype_2 }}
                </el-tag>
              </div>
            </div>

            <div v-if="mouse.genotypes && mouse.genotypes.length > 0" class="space-y-2 max-h-[160px] overflow-y-auto pr-1">
              <div
                v-for="gt in mouse.genotypes"
                :key="gt.id"
                class="border border-gray-200 bg-white rounded-lg p-2.5 text-xs space-y-1 shadow-2xs"
              >
                <div class="flex items-center justify-between">
                  <span class="font-mono text-gray-600 font-medium">📅 测试日期: {{ gt.test_date || '未记录' }}</span>
                  <div class="flex gap-1">
                    <el-tag size="small" type="success">{{ gt.genotype_1 || '已鉴定' }}</el-tag>
                    <el-tag v-if="gt.genotype_2" size="small" type="warning">{{ gt.genotype_2 }}</el-tag>
                    <el-tag v-if="gt.genotype_3" size="small" type="info">{{ gt.genotype_3 }}</el-tag>
                  </div>
                </div>
                <div v-if="gt.parents" class="text-purple-700 font-mono text-[11px] flex items-center gap-1.5 mt-1">
                  <span>系谱记录:</span>
                  <PedigreeTags :parents="gt.parents" @click-parent="navigateToParent" />
                </div>
                <div v-if="gt.op_record || gt.notes" class="text-gray-500 text-[11px] flex items-center gap-2">
                  <span v-if="gt.op_record">操作人: {{ gt.op_record }}</span>
                  <span v-if="gt.notes">备注: {{ gt.notes }}</span>
                </div>
              </div>
            </div>
            <div v-else-if="mouse.genotype_1" class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-600 flex justify-between items-center">
              <span>记录基因型: <b class="text-emerald-700">{{ mouse.genotype_1 }}</b> <span v-if="mouse.genotype_2">/ {{ mouse.genotype_2 }}</span></span>
              <span class="text-gray-400 font-mono">{{ mouse.test_date || '测试日期未详' }}</span>
            </div>
            <div v-else class="text-xs text-gray-400 text-center py-3 bg-gray-50 rounded-lg border border-dashed border-gray-200">
              暂无该小鼠的 PCR 基因鉴定记录
            </div>
          </div>

          <!-- Section 3: Transfer & Cage Logs (流转记录) -->
          <div v-if="mouse.transfer_logs && mouse.transfer_logs.length > 0">
            <div class="text-xs font-bold text-gray-700 mb-2 flex items-center gap-1.5">
              <span>📋 流转与领用日志 ({{ mouse.transfer_logs.length }})</span>
            </div>
            <div class="space-y-1.5 max-h-[120px] overflow-y-auto pr-1">
              <div
                v-for="log in mouse.transfer_logs"
                :key="log.id"
                class="text-xs bg-gray-50 border border-gray-200 rounded p-2 flex justify-between items-center"
              >
                <div>
                  <span class="font-bold text-blue-700">[{{ log.action_type }}]</span>
                  <span v-if="log.claimer_name" class="ml-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-semibold border" :style="getClaimerTagStyle(log.claimer_name)">
                    👤 {{ log.claimer_name }}
                  </span>
                  <span v-if="log.source_room || log.source_cage || log.target_room || log.target_cage" class="ml-1.5 text-gray-600">
                    <template v-if="log.source_room || log.source_cage">{{ log.source_room }} {{ log.source_cage }}</template>
                    <template v-if="log.target_room || log.target_cage">
                      <span v-if="log.source_room || log.source_cage"> → </span>
                      <span v-else>转移至: </span>
                      {{ log.target_room }} {{ log.target_cage }}
                    </template>
                  </span>
                  <span v-if="log.notes" class="ml-1.5 text-gray-400 text-[11px]">({{ log.notes }})</span>
                </div>
                <span class="text-gray-400 text-[11px] font-mono">{{ log.date || log.created_at || '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Empty / Error state -->
      <div v-else-if="!loading" class="py-12 text-center text-gray-400 text-sm">
        <span class="text-3xl block mb-2">📋</span>
        未找到小鼠相关档案信息
      </div>
    </div>

    <template #footer>
      <div v-if="!isEditing" class="flex justify-between items-center w-full">
        <div class="flex items-center gap-2">
          <el-button
            v-if="authStore.isAdmin && mouse"
            type="primary"
            size="small"
            @click="startEdit"
          >
            ✏️ 编辑档案
          </el-button>
          <el-button
            v-if="authStore.isAdmin && mouse && mouse.id"
            type="default"
            size="small"
            @click="handleSetOwner"
          >
            👤 指定 / 变更领取人
          </el-button>
        </div>
        <el-button @click="visible = false">关 闭</el-button>
      </div>

      <div v-else class="flex justify-between items-center w-full">
        <span class="text-xs text-gray-500">点击「保存档案」后即刻同步全系统</span>
        <div class="flex items-center gap-2">
          <el-button size="small" @click="cancelEdit">取消</el-button>
          <el-button size="small" type="primary" :loading="saveLoading" @click="saveEdit">
            保存档案
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
  <CageDetailDialog v-model="showCageDetail" :cage-id="selectedCageId" @refresh="onCageChanged" />
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { miceApi, cagesApi, claimersApi, mouseStatusesApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClaimerColors } from '@/composables/useClaimerColors'
import { ElMessage } from 'element-plus'
import PedigreeTags from './PedigreeTags.vue'
import CageDetailDialog from './CageDetailDialog.vue'
import { isClaimedOutOfCage, mouseStatusLabel } from '@/utils/mouseDisplay'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  mouseCode: {
    type: String,
    default: ''
  },
  mouseId: {
    type: [Number, String],
    default: null
  },
  initialData: {
    type: Object,
    default: null
  },
  startInEditMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'setOwner', 'refresh', 'updated'])

const authStore = useAuthStore()
const { getClaimerTagStyle } = useClaimerColors()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const mouse = ref(null)
const showCageDetail = ref(false)
const selectedCageId = ref(null)

function openCageDetail() {
  selectedCageId.value = mouse.value.cage_id
  showCageDetail.value = true
}

async function onCageChanged() {
  emit('refresh')
  if (mouse.value) {
    await fetchMouseData(mouse.value.mouse_code, mouse.value.id)
    emit('updated', mouse.value)
  }
}

// Editing state & options
const isEditing = ref(false)
const saveLoading = ref(false)
const editStrainOptions = ref([])
const editRoomOptions = ref([])
const editClaimerOptions = ref([])

const ALL_STATUSES = ref([])

const editForm = reactive({
  mouse_code: '',
  strain: '',
  gender: 'M',
  status: '在笼',
  dob: '',
  parents: '',
  genotype_1: '',
  genotype_2: '',
  source_room: '',
  cage_code: '',
  owner_name: '',
  claim_date: '',
  claim_purpose: '',
  notes: ''
})

async function loadEditOptions() {
  try {
    const [strains, rooms, claimers, statuses] = await Promise.all([
      miceApi.getAllStrains().catch(() => []),
      cagesApi.listRooms().catch(() => []),
      claimersApi.listClaimers().catch(() => []),
      mouseStatusesApi.listStatuses().catch(() => [])
    ])
    editStrainOptions.value = strains || []
    editRoomOptions.value = rooms || []
    editClaimerOptions.value = claimers || []
    ALL_STATUSES.value = (statuses || []).map(status => ({
      label: status.name,
      value: status.name,
      type: status.removes_from_cage ? 'danger' : (
        status.name === '已领用' ? 'success' : (status.name === '在笼' ? 'primary' : 'info')
      )
    }))
  } catch (e) {
    console.warn('Failed to load edit options', e)
  }
}

function startEdit() {
  if (!mouse.value) return
  Object.assign(editForm, {
    mouse_code: mouse.value.mouse_code || '',
    strain: mouse.value.strain || '',
    gender: mouse.value.gender || 'M',
    status: mouse.value.id ? (mouse.value.status || '在笼') : '在笼',
    dob: mouse.value.dob || '',
    parents: mouse.value.parents || '',
    genotype_1: mouse.value.genotype_1 || '',
    genotype_2: mouse.value.genotype_2 || '',
    source_room: mouse.value.cage_room || mouse.value.source_room || '',
    cage_code: mouse.value.cage_code || '',
    owner_name: mouse.value.owner_name || '',
    claim_date: mouse.value.claim_date || '',
    claim_purpose: mouse.value.claim_purpose || '',
    notes: mouse.value.notes || ''
  })
  isEditing.value = true
  loadEditOptions()
}

function cancelEdit() {
  isEditing.value = false
}

async function saveEdit() {
  if (saveLoading.value) return
  if (!editForm.mouse_code.trim()) {
    ElMessage.warning('耳标编号不能为空')
    return
  }
  saveLoading.value = true
  try {
    const payload = {
      mouse_code: editForm.mouse_code.trim(),
      strain: editForm.strain ? editForm.strain.trim() : undefined,
      gender: editForm.gender,
      status: editForm.status,
      dob: editForm.dob || undefined,
      parents: editForm.parents || undefined,
      genotype_1: editForm.genotype_1 || undefined,
      genotype_2: editForm.genotype_2 || undefined,
      source_room: editForm.source_room || undefined,
      cage_code: editForm.cage_code || undefined,
      owner_name: editForm.owner_name || undefined,
      claim_date: editForm.claim_date || undefined,
      claim_purpose: editForm.claim_purpose || undefined,
      notes: editForm.notes || undefined
    }
    const res = mouse.value.id
      ? await miceApi.updateMouse(mouse.value.id, payload)
      : await miceApi.createMouse({ ...payload, test_date: mouse.value.test_date || undefined })
    mouse.value = res
    ElMessage.success(`小鼠 [${res.mouse_code}] 档案已成功更新`)
    isEditing.value = false
    emit('updated', res)
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存小鼠档案失败')
  } finally {
    saveLoading.value = false
  }
}

const dialogTitle = computed(() => {
  if (isEditing.value) {
    return `编辑小鼠档案 - [${mouse.value?.mouse_code || props.mouseCode}]`
  }
  if (mouse.value?.mouse_code) {
    return `小鼠档案详情 - [${mouse.value.mouse_code}]`
  }
  if (props.mouseCode) {
    return `小鼠档案详情 - [${props.mouseCode}]`
  }
  return '小鼠详细档案'
})

// Intelligently parse parents into father & mother badges
const parsedParents = computed(() => {
  const p = mouse.value?.parents
  if (!p) return []
  const results = []
  // E.g. 'E925M+E822F、E824F' or 'B311M+B354F'
  const cleaned = p.replace(/[\(（].*?[\)）]/g, '')
  const parts = cleaned.split(/[+、/,，\s\\]+/)
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed || trimmed.includes('无') || trimmed.includes('新品系') || trimmed.includes('不明') || trimmed.includes('集萃') || trimmed.includes('外购')) continue
    const m = trimmed.match(/^([A-Za-z0-9_-]+?)([MFmf])$/)
    if (m) {
      const code = m[1].trim()
      const gender = m[2].toUpperCase()
      if (!['HO', 'KO', 'CAS', 'GF', 'BF', 'WT'].includes(code.toUpperCase())) {
        results.push({
          code,
          gender
        })
        continue
      }
    }
    if (/^[A-Za-z0-9_-]{2,10}$/.test(trimmed) && !/^[A-Za-z]+$/.test(trimmed)) {
      results.push({
        code: trimmed,
        gender: null
      })
    }
  }
  return results
})

function getStatusType(status) {
  return ALL_STATUSES.value.find(item => item.value === status)?.type || 'info'
}

// Traversal history stack for lineage navigation
const navHistory = ref([])

function navigateToParent(parentCode) {
  if (!parentCode) return
  isEditing.value = false
  if (mouse.value) {
    navHistory.value.push({
      code: mouse.value.mouse_code,
      id: mouse.value.id
    })
  }
  fetchMouseData(parentCode, null)
}

function goBack() {
  isEditing.value = false
  if (navHistory.value.length > 0) {
    const prev = navHistory.value.pop()
    fetchMouseData(prev.code, prev.id)
  }
}

function goToHistory(idx) {
  isEditing.value = false
  const target = navHistory.value[idx]
  navHistory.value = navHistory.value.slice(0, idx)
  fetchMouseData(target.code, target.id)
}

async function fetchMouseData(code, id = null) {
  loading.value = true
  try {
    let res = null
    if (id) {
      res = await miceApi.getMouse(id)
    } else if (code) {
      res = await miceApi.getMouseByCode(code)
    }
    if (res) {
      mouse.value = res
    }
  } catch (e) {
    ElMessage.warning(`未找到耳标 [${code}] 的档案记录`)
  } finally {
    loading.value = false
  }
}

async function loadData() {
  if (!visible.value) return
  isEditing.value = false

  if (props.initialData) {
    mouse.value = { ...props.initialData }
  }

  loadEditOptions()
  await fetchMouseData(props.mouseCode, props.mouseId)
  if (props.startInEditMode && mouse.value) {
    startEdit()
  }
}

watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    navHistory.value = []
    isEditing.value = false
    loadData()
  } else {
    mouse.value = null
    navHistory.value = []
    isEditing.value = false
  }
})

watch(() => props.mouseCode, () => {
  if (visible.value) {
    navHistory.value = []
    isEditing.value = false
    loadData()
  }
})

watch(() => props.mouseId, () => {
  if (visible.value) {
    navHistory.value = []
    isEditing.value = false
    loadData()
  }
})

function handleSetOwner() {
  if (mouse.value) {
    emit('setOwner', mouse.value)
    visible.value = false
  }
}
</script>

<style scoped>
.mouse-detail-body {
  min-height: 180px;
}
</style>

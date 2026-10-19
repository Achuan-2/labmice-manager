<template>
  <div class="mice-page">
    <div class="mouse-search-bar mb-4">
      <el-input
        v-model="filters.keyword"
        placeholder="搜索耳标、品系、基因型或备注"
        clearable
        prefix-icon="Search"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
    </div>

    <!-- Action Bar -->
    <div class="bg-white p-3 rounded-xl shadow-sm border border-gray-200 mb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <!-- Core Action Button: Batch Set Owner -->
        <el-button
          type="primary"
          :disabled="selectedMice.length === 0 || !authStore.isAdmin"
          @click="openSetOwnerDialog(selectedMice)"
        >
          <el-icon class="mr-1"><User /></el-icon>
          批量设置领取人 (已选 {{ selectedMice.length }} 只)
        </el-button>

        <el-button
          :disabled="selectedMice.length === 0 || !authStore.isAdmin"
          @click="showTransferDialog = true"
        >
          <el-icon class="mr-1"><Van /></el-icon>
          批量转房 / 换笼
        </el-button>

        <el-dropdown
          trigger="click"
          :disabled="selectedMice.length === 0 || !authStore.isAdmin"
          @command="handleBatchStatus"
        >
          <el-button :disabled="selectedMice.length === 0 || !authStore.isAdmin">
            状态标记 <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="st in ALL_STATUSES" :key="st.value" :command="st.value">
                <span class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded-full" :class="st.dotClass"></span>
                  标记为 [{{ st.label }}]
                </span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <div class="flex items-center gap-2">
        <el-button v-if="authStore.isAdmin" plain @click="showStatusManager = true">
          <el-icon class="mr-1"><Setting /></el-icon> 状态管理
        </el-button>
        <el-button v-if="authStore.isAdmin" type="success" plain @click="openAddMouseDialog">
          <el-icon class="mr-1"><Plus /></el-icon> 录入新小鼠
        </el-button>
        <el-button :loading="exporting" @click="handleExport">
          <el-icon class="mr-1"><Download /></el-icon> 导出 Excel
        </el-button>
      </div>
    </div>

    <!-- Mice Table -->
    <div v-if="authStore.isAdmin" class="text-xs text-gray-500 mb-2" role="status">
      {{ gridSaving ? '正在保存小鼠资料…' : fillDrag ? `松开鼠标，将填充 ${Math.abs(fillDrag.endIndex - fillDrag.startIndex)} 只小鼠` : '点击列标题可筛选、排序；点击资料格直接编辑，修改后自动保存。保存后拖动右下角蓝色方块可填充当前页同列，覆盖原值；Esc 取消编辑或拖动。编辑时保持行位置，查询或翻页后刷新筛选。' }}
    </div>
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table
        v-loading="loading || gridSaving"
        :data="miceList"
        row-key="id"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />

        <el-table-column prop="mouse_code" label="耳标 / 编号" width="140" fixed>
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps('mouse_code', '耳标 / 编号')" v-on="columnMenuEvents('mouse_code')" />
          </template>
          <template #default="{ row }">
            <div
              class="inline-flex items-center cursor-pointer text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded transition-colors group"
              title="点击查看小鼠完整档案、系谱及变动记录"
              @click="openMouseDetail(row)"
            >
              <span class="font-bold font-mono text-sm underline-offset-2 group-hover:underline">
                {{ row.mouse_code }}
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column v-for="column in mouseInfoColumns" :key="column.field" :prop="column.field" :label="column.label" :min-width="column.width">
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps(column.field, column.label)" v-on="columnMenuEvents(column.field)" />
          </template>
          <template #default="{ row, $index }">
            <GenotypeGridCell v-bind="gridCellProps(row, column.field, $index)" v-on="gridCellEvents(row, column.field, $index)">
              <template v-if="column.field === 'strain'">
                <span class="font-semibold text-blue-700">{{ row.strain || '-' }}</span>
              </template>
              <template v-else-if="column.field === 'gender'">
                <el-tag v-if="row.gender === 'M'" size="small" type="primary">♂ 雄</el-tag>
                <el-tag v-else-if="row.gender === 'F'" size="small" type="danger">♀ 雌</el-tag>
                <el-tag v-else size="small" type="info">未知</el-tag>
              </template>
              <div v-else-if="column.field === 'dob'" class="text-xs">
                <span class="text-gray-700 font-mono">{{ row.dob || '-' }}</span>
                <span v-if="row.age_weeks != null" class="ml-1.5 font-bold text-emerald-600">({{ row.age_weeks }} 周)</span>
              </div>
              <PedigreeTags v-else :parents="row.parents" @click-parent="openMouseDetail" />
            </GenotypeGridCell>
          </template>
        </el-table-column>

        <!-- Direct Genotype Linkage Column -->
        <el-table-column label="基因鉴定结果" min-width="150">
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps('genotype_1', '基因鉴定结果')" v-on="columnMenuEvents('genotype_1')" />
          </template>
          <template #default="{ row }">
            <div v-if="row.genotypes && row.genotypes.length > 0" class="flex items-center gap-1">
              <el-tag
                size="small"
                :type="mouseGenotypeLabel(row) === '待鉴定' ? 'warning' : 'success'"
                effect="plain"
                class="cursor-pointer hover:opacity-80"
                @click="viewGenotypes(row)"
              >
                🔬 {{ mouseGenotypeLabel(row) }}
                <span v-if="row.genotypes.length > 1" class="text-xs ml-0.5">({{ row.genotypes.length }})</span>
              </el-tag>
            </div>
            <div v-else-if="row.genotype_1">
              <el-tag size="small" :type="mouseGenotypeLabel(row) === '待鉴定' ? 'warning' : 'info'">{{ mouseGenotypeLabel(row) }}</el-tag>
            </div>
            <div v-else class="text-xs text-gray-300">待鉴定</div>
          </template>
        </el-table-column>

        <el-table-column label="当前笼位与鼠房" min-width="160">
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps('cage_code', '当前笼位与鼠房')" v-on="columnMenuEvents('cage_code')" />
          </template>
          <template #default="{ row }">
            <div v-if="row.cage_code" class="flex items-center gap-1.5">
              <el-tag size="small" effect="plain" type="info">{{ row.cage_room }}</el-tag>
              <el-button
                type="primary"
                link
                size="small"
                class="font-mono font-bold"
                title="点击查看笼位详情"
                @click="openCageDetail(row)"
              >
                [{{ row.cage_code }}]
              </el-button>
            </div>
            <div v-else-if="isClaimedOutOfCage(row)" class="text-xs text-gray-500">
              {{ row.source_room }} (出笼)
            </div>
            <div v-else-if="row.source_room" class="text-xs text-gray-400">
              {{ row.source_room }} (未入笼)
            </div>
            <div v-else class="text-xs text-gray-300">-</div>
          </template>
        </el-table-column>

        <!-- Core Linkage Column: Owner / Claimer -->
        <el-table-column label="当前领取人" min-width="165">
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps('owner_name', '当前领取人')" v-on="columnMenuEvents('owner_name')" />
          </template>
          <template #default="{ row, $index }">
            <GenotypeGridCell v-bind="gridCellProps(row, 'owner_name', $index)" v-on="gridCellEvents(row, 'owner_name', $index)">
              <div v-if="row.owner_name" class="flex items-center gap-1">
                <el-tag size="small" :style="getClaimerTagStyle(row.owner_name)" class="font-medium border">
                  👤 {{ row.owner_name }}
                </el-tag>
              </div>
              <div v-else>
                <el-tag size="small" type="info" effect="plain" class="text-gray-400">未分配</el-tag>
              </div>
            </GenotypeGridCell>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" min-width="135">
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps('status', '状态')" v-on="columnMenuEvents('status')" />
          </template>
          <template #default="{ row, $index }">
            <GenotypeGridCell v-bind="gridCellProps(row, 'status', $index)" v-on="gridCellEvents(row, 'status', $index)">
              <el-tag size="small" :type="getStatusType(row.status)">{{ mouseStatusLabel(row) }}</el-tag>
            </GenotypeGridCell>
          </template>
        </el-table-column>

        <el-table-column v-for="column in noteColumns" :key="column.field" :prop="column.field" :label="column.label" min-width="180">
          <template #header>
            <MouseColumnHeader v-bind="columnMenuProps(column.field, column.label)" v-on="columnMenuEvents(column.field)" />
          </template>
          <template #default="{ row, $index }">
            <GenotypeGridCell v-bind="gridCellProps(row, column.field, $index)" v-on="gridCellEvents(row, column.field, $index)">
              <span class="text-xs text-gray-600 truncate" :title="row[column.field]">{{ row[column.field] || '-' }}</span>
            </GenotypeGridCell>
          </template>
        </el-table-column>

        <!-- Action Column -->
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center gap-1">
              <el-button
                v-if="!row.owner_name"
                size="small"
                type="primary"
                link
                :disabled="!authStore.isAdmin"
                @click="openSetOwnerDialog([row])"
              >
                设置领取人
              </el-button>
              <el-button
                size="small"
                type="info"
                link
                :disabled="!authStore.isAdmin"
                @click="openEditDialog(row)"
              >
                编辑
              </el-button>
              <el-popconfirm
                title="确定删除此小鼠档案吗？"
                @confirm="handleDeleteMouse(row.id)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    type="danger"
                    link
                    :disabled="!authStore.isAdmin"
                  >
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="p-3 border-t border-gray-100 flex items-center justify-between">
        <div class="text-xs text-gray-500">
          共 <span class="font-bold text-gray-800">{{ total }}</span> 只小鼠记录
        </div>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadMice"
          @current-change="loadMice"
        />
      </div>
    </div>

    <!-- Mouse Genotype History Drawer -->
    <el-drawer
      v-model="showGenotypeDrawer"
      :title="`小鼠 [${activeMouse?.mouse_code}] 基因鉴定档案`"
      size="520px"
    >
      <div v-if="activeMouse" class="space-y-4">
        <div class="bg-gray-50 p-3 rounded-lg text-xs space-y-1 text-gray-700">
          <div>耳标编号: <b class="font-mono">{{ activeMouse.mouse_code }}</b></div>
          <div>品系: <b>{{ activeMouse.strain }}</b> | 性别: <b>{{ activeMouse.gender }}</b></div>
          <div v-if="activeMouse.parents" class="flex items-center gap-1.5">
            <span>父母系谱:</span>
            <PedigreeTags :parents="activeMouse.parents" @click-parent="openMouseDetail" />
          </div>
        </div>

        <div class="font-bold text-sm text-gray-800">鉴定历史记录 ({{ activeMouse.genotypes?.length || 0 }} 次):</div>

        <div v-if="!activeMouse.genotypes || activeMouse.genotypes.length === 0" class="text-gray-400 text-xs text-center py-6">
          暂无该小鼠的独立鉴定记录
        </div>

        <div
          v-for="gt in activeMouse.genotypes"
          :key="gt.id"
          class="border border-gray-200 rounded-lg p-3 text-xs space-y-1.5 bg-white shadow-sm"
        >
          <div class="flex justify-between items-center">
            <span class="text-gray-500 font-mono">📅 测试日期: {{ gt.test_date || '未记录' }}</span>
            <el-tag size="small" :type="hasGenotypeResult(gt) ? 'success' : 'warning'">{{ hasGenotypeResult(gt) ? '已鉴定' : '待鉴定' }}</el-tag>
          </div>
          <div v-if="hasGenotypeResult({ genotype_1: gt.genotype_1 })">Genotype 1: <span class="font-semibold">{{ gt.genotype_1 }}</span></div>
          <div v-if="gt.parents || activeMouse.parents" class="text-purple-700 font-mono flex items-center gap-1.5">
            <span>父母系谱:</span>
            <PedigreeTags :parents="gt.parents || activeMouse.parents" @click-parent="openMouseDetail" />
          </div>
          <div v-if="gt.genotype_2">Genotype 2: <span class="font-semibold">{{ gt.genotype_2 }}</span></div>
          <div v-if="gt.genotype_3">Genotype 3: <span class="font-semibold">{{ gt.genotype_3 }}</span></div>
          <div v-if="gt.op_record">操作记录/人员: <span class="text-gray-600">{{ gt.op_record }}</span></div>
          <div v-if="gt.notes">备注: <span class="text-gray-600">{{ gt.notes }}</span></div>
        </div>
      </div>
    </el-drawer>

    <!-- Set Owner Dialog Component -->
    <SetOwnerDialog
      v-model="showSetOwnerDialog"
      :mice="currentOperatingMice"
      @success="onBatchSuccess"
    />

    <!-- Batch Transfer Dialog -->
    <el-dialog v-model="showTransferDialog" title="批量转移鼠房与笼位" width="460px">
      <el-form label-width="90px">
        <el-form-item label="目标鼠房" required>
          <el-select v-model="transferForm.target_room" filterable allow-create default-first-option placeholder="选择目标鼠房或输入新鼠房" style="width: 100%">
            <el-option v-for="r in roomOptions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标笼号">
          <el-input v-model="transferForm.target_cage_code" placeholder="如 H9, 7A (选填，若不存在自动创建)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTransferDialog = false">取消</el-button>
        <el-button type="primary" @click="submitBatchTransfer">确认转移</el-button>
      </template>
    </el-dialog>

    <!-- Add Mouse Dialog -->
    <el-dialog v-model="showAddMouseDialog" title="录入新小鼠 (支持批量)" width="570px" align-center>
      <el-form :model="mouseForm" label-width="110px">
        <el-form-item label="新增数量" required>
          <el-input-number v-model="mouseForm.add_count" :min="1" :max="100" @change="updateMouseCodes" />
        </el-form-item>
        <el-form-item label="起始编号" required>
          <el-input v-model="mouseForm.start_code" placeholder="如 Z100" @input="updateMouseCodes" />
          <div class="text-xs text-gray-500">起始编号包含在本批内；输入 Z100、新增 5 只，将生成 Z100 至 Z104。</div>
        </el-form-item>
        <el-form-item label="编号列表" required>
          <el-input
            v-model="mouseForm.mouse_code"
            type="textarea"
            :rows="2"
            placeholder="自动生成后仍可手动调整，多个编号用空格或中英文逗号分隔"
          />
        </el-form-item>
        <el-form-item label="品系/基因" required>
          <el-select
            v-model="mouseForm.strain"
            filterable
            allow-create
            default-first-option
            placeholder="选择已有品系或直接输入新增品系"
            style="width: 100%"
          >
            <el-option v-for="s in strainOptions" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="mouseForm.gender">
            <el-radio value="M">雄 (M)</el-radio>
            <el-radio value="F">雌 (F)</el-radio>
            <el-radio value="未知">未知</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="出生日期">
          <el-date-picker v-model="mouseForm.dob" type="date" value-format="YYYY-MM-DD" placeholder="选择出生日期" />
        </el-form-item>
        <el-form-item label="父母系谱">
          <el-input
            v-model="mouseForm.parents"
            placeholder="如 E925+E822（可直接输入耳标，系统自动判定性别）"
            clearable
            @blur="handleParentsBlur"
          />
          <!-- Smart Parent Detection helper -->
          <div
            v-if="parentsDetection && parentsDetection.details && parentsDetection.details.length > 0"
            class="mt-1.5 p-2 bg-purple-50/80 border border-purple-200/70 rounded-lg text-xs flex items-center justify-between shadow-2xs w-full"
          >
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="text-purple-800 font-bold flex items-center gap-1">🧬 识别亲本:</span>
              <span
                v-for="p in parentsDetection.details"
                :key="p.code"
                class="parent-reference px-2 py-0.5 rounded-full text-xs font-mono font-bold shadow-2xs inline-flex items-center gap-1 cursor-pointer transition"
                :class="p.gender === 'M' ? 'bg-blue-100 text-blue-800 border border-blue-200' : (p.gender === 'F' ? 'bg-pink-100 text-pink-800 border border-pink-200' : 'bg-gray-100 text-gray-700 border border-gray-200')"
                :title="`点击查看亲本 ${p.code} 的小鼠档案详情`"
                @click.stop="openMouseDetail(p.code)"
              >
                <span>{{ p.gender === 'M' ? '♂ 父本' : (p.gender === 'F' ? '♀ 母本' : '亲本') }}</span>
                <span>{{ p.code }}</span>
                <span v-if="p.gender" class="text-[10px] opacity-75">({{ p.gender }})</span>
                <span v-else class="text-[10px] text-gray-400">(未录入性别)</span>
              </span>
            </div>
            <div v-if="parentsDetection.has_changes">
              <el-button
                size="small"
                type="primary"
                link
                @click="mouseForm.parents = parentsDetection.normalized"
              >
                补齐格式: {{ parentsDetection.normalized }}
              </el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="基因鉴定结果">
          <el-input v-model="mouseForm.genotype_1" placeholder="如 阳性, 野生型, 杂合子, 纯合子" />
        </el-form-item>
        <el-form-item label="所在鼠房">
          <el-select
            v-model="mouseForm.source_room"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入新鼠房"
            style="width: 100%"
          >
            <el-option v-for="r in roomOptions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="mouseForm.status"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入新状态"
            style="width: 100%"
          >
            <el-option v-for="st in ALL_STATUSES" :key="st.value" :label="st.label" :value="st.value" />
          </el-select>
          <div class="text-xs text-gray-400 mt-1">可选择已有状态，也可输入新状态后回车创建</div>
        </el-form-item>
        <el-form-item label="领取人">
          <el-select v-model="mouseForm.owner_name" filterable clearable placeholder="可选指定领取人" style="width: 100%">
            <el-option v-for="c in claimerOptions" :key="c.name" :label="c.name" :value="c.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="mouseForm.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMouseDialog = false">取消</el-button>
        <el-button type="primary" @click="submitAddMouseForm">
          {{ detectedCodesCount > 1 ? `批量录入 (${detectedCodesCount}只)` : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Mouse Detail Modal -->
    <MouseDetailModal
      v-model="showMouseDetailModal"
      :mouse-code="detailMouseCode"
      :mouse-id="detailMouseId"
      :start-in-edit-mode="detailStartInEditMode"
      @set-owner="openSetOwnerFromDetail"
      @refresh="onBatchSuccess"
    />
    <MouseStatusManager
      v-model="showStatusManager"
      @changed="handleStatusesChanged"
    />
    <CageDetailDialog
      v-model="showCageDetail"
      :cage-id="selectedCageId"
      @refresh="onBatchSuccess"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { miceApi, cagesApi, claimersApi, mouseStatusesApi, importExportApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClaimerColors } from '@/composables/useClaimerColors'
import SetOwnerDialog from '@/components/SetOwnerDialog.vue'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import MouseStatusManager from '@/components/MouseStatusManager.vue'
import CageDetailDialog from '@/components/CageDetailDialog.vue'
import { hasGenotypeResult, isClaimedOutOfCage, mouseStatusLabel, mouseGenotypeLabel } from '@/utils/mouseDisplay'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'
import PedigreeTags from '@/components/PedigreeTags.vue'
import GenotypeGridCell from '@/components/GenotypeGridCell.vue'
import MouseColumnHeader from '@/components/MouseColumnHeader.vue'
import { useGridFill } from '@/composables/useGridFill'
import { apiErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'

const route = useRoute()
const authStore = useAuthStore()
const { getClaimerTagStyle, fetchClaimerColors } = useClaimerColors()

const loading = ref(false)
const exporting = ref(false)
const miceList = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const selectedMice = ref([])
const gridSaving = ref(false)
const { activeCell, fillDrag, activateCell, startFill, extendFill, isInFillRange, cancelFill } = useGridFill(
  miceList, () => gridSaving.value || loading.value || !authStore.isAdmin, saveGridValues,
)
let loadRequestId = 0

const mouseInfoColumns = [
  { field: 'strain', label: '品系 / 基因型', width: 180 },
  { field: 'gender', label: '性别', width: 110 },
  { field: 'dob', label: '出生日期 / 周龄', width: 190 },
  { field: 'parents', label: '父母系谱 (M+F)', width: 230 },
]
const noteColumns = [{ field: 'claim_purpose', label: '领用用途' }, { field: 'notes', label: '备注' }]

const mouseSortFields = ['added', 'mouse_code', 'dob', 'strain', 'gender', 'parents', 'genotype_1', 'cage_code', 'owner_name', 'status', 'claim_purpose', 'notes']
const savedSortBy = localStorage.getItem('mice_sort_by')
const savedSortOrder = localStorage.getItem('mice_sort_order')
const sortBy = ref(mouseSortFields.includes(savedSortBy) ? savedSortBy : 'added')
const sortOrder = ref(['asc', 'desc'].includes(savedSortOrder) ? savedSortOrder : 'desc')
watch([sortBy, sortOrder], ([by, order]) => {
  localStorage.setItem('mice_sort_by', by)
  localStorage.setItem('mice_sort_order', order)
})

const roomOptions = ref([])
const strainOptions = ref([])
const parentOptions = ref([])
const claimerOptions = ref([])
const emptyFilters = {
  keyword: '',
  mouse_code: '',
  room: '',
  cage_code: '',
  strain: '',
  parents: [],
  gender: '',
  owner_name: '',
  status: '',
  has_owner: null,
  in_cage: null,
  dob_from: '',
  dob_to: '',
  age_weeks_gt: null,
  age_weeks_lt: null,
  genotype: '',
  test_status: '',
  claim_purpose: '',
  notes: '',
}
const filters = reactive({ ...emptyFilters, parents: [] })

// Dialog States
const showSetOwnerDialog = ref(false)
const currentOperatingMice = ref([])
const showTransferDialog = ref(false)
const showAddMouseDialog = ref(false)
const showStatusManager = ref(false)

// Mouse detail modal
const showMouseDetailModal = ref(false)
const detailMouseCode = ref('')
const detailMouseId = ref(null)
const detailStartInEditMode = ref(false)
const showCageDetail = ref(false)
const selectedCageId = ref(null)

function openMouseDetail(rowOrCode) {
  detailStartInEditMode.value = false
  if (typeof rowOrCode === 'string') {
    detailMouseCode.value = rowOrCode
    detailMouseId.value = null
  } else {
    detailMouseCode.value = rowOrCode?.mouse_code || ''
    detailMouseId.value = rowOrCode?.id || null
  }
  showMouseDetailModal.value = true
}

function openCageDetail(row) {
  if (!row?.cage_id) return
  selectedCageId.value = row.cage_id
  showCageDetail.value = true
}

function openSetOwnerFromDetail(mouse) {
  openSetOwnerDialog([mouse])
}

// Genotype Drawer
const showGenotypeDrawer = ref(false)
const activeMouse = ref(null)

const transferForm = reactive({
  target_room: '',
  target_cage_code: ''
})

const mouseForm = reactive({
  add_count: 1,
  start_code: '',
  mouse_code: '',
  strain: '',
  gender: 'M',
  dob: '',
  parents: '',
  genotype_1: '',
  source_room: '',
  cage_code: '',
  status: '在笼',
  owner_name: '',
  notes: ''
})

const ALL_STATUSES = ref([])

const columnControls = computed(() => {
  const options = values => values.map(value => ({ value, label: value }))
  return {
    mouse_code: [{ key: 'mouse_code', label: '耳标编号', placeholder: '输入完整耳标编号' }],
    strain: [{ key: 'strain', label: '品系', type: 'select', options: options(strainOptions.value) }],
    gender: [{ key: 'gender', label: '性别', type: 'select', options: gridOptions.value.gender }],
    dob: [
      { key: 'age_weeks_gt', label: '周龄大于（周）', type: 'number' },
      { key: 'age_weeks_lt', label: '周龄小于（周）', type: 'number' },
      { key: 'dob_from', label: '出生日期起始', type: 'date' },
      { key: 'dob_to', label: '出生日期截止', type: 'date' },
    ],
    parents: [{ key: 'parents', label: '亲本编号', type: 'select', multiple: true,
      options: parentOptions.value.map(value => ({ value, label: parentOptionLabel(value) })) }],
    genotype_1: [
      { key: 'genotype', label: '鉴定结果', placeholder: '输入结果关键词' },
      { key: 'test_status', label: '鉴定状态', type: 'select', options: [{ value: 'pending', label: '待鉴定' }, { value: 'tested', label: '已鉴定' }] },
    ],
    cage_code: [
      { key: 'room', label: '鼠房', type: 'select', options: options(roomOptions.value) },
      { key: 'cage_code', label: '笼号', placeholder: '输入完整笼号' },
      { key: 'in_cage', label: '入笼情况', type: 'select', options: [{ value: true, label: '已入笼' }, { value: false, label: '未入笼' }] },
    ],
    owner_name: [
      { key: 'owner_name', label: '领取人', type: 'select', options: options(claimerOptions.value.map(item => item.name)) },
      { key: 'has_owner', label: '领用情况', type: 'select', options: [{ value: false, label: '未领用（待分配）' }, { value: true, label: '已领用' }] },
    ],
    status: [{ key: 'status', label: '状态', type: 'select', options: ALL_STATUSES.value }],
    claim_purpose: [{ key: 'claim_purpose', label: '领用用途', placeholder: '输入用途关键词' }],
    notes: [{ key: 'notes', label: '备注', placeholder: '输入备注关键词' }],
  }
})

function hasFilterValue(value) {
  return Array.isArray(value) ? value.length > 0 : value !== null && value !== undefined && value !== ''
}

function columnMenuProps(field, label) {
  const controls = columnControls.value[field]
  const modelValue = Object.fromEntries(controls.map(control => [control.key, filters[control.key]]))
  return {
    label, controls, modelValue,
    filtered: Object.values(modelValue).some(hasFilterValue),
    anyFiltered: Object.values(filters).some(hasFilterValue),
    sortOrder: sortBy.value === field ? sortOrder.value : '',
  }
}

function columnMenuEvents(field) {
  return {
    filter: values => {
      if (values.age_weeks_gt != null && values.age_weeks_lt != null && values.age_weeks_gt >= values.age_weeks_lt) {
        ElMessage.warning('周龄下限必须小于上限')
        return
      }
      if (values.dob_from && values.dob_to && values.dob_from > values.dob_to) {
        ElMessage.warning('出生日期起始不能晚于截止日期')
        return
      }
      for (const control of columnControls.value[field]) {
        filters[control.key] = values[control.key] ?? (control.multiple ? [] : emptyFilters[control.key])
      }
      handleSearch()
    },
    sort: order => { sortBy.value = field; sortOrder.value = order; handleSearch() },
    'reset-sort': () => { sortBy.value = 'added'; sortOrder.value = 'desc'; handleSearch() },
    'reset-filters': resetFilters,
  }
}

const gridOptions = computed(() => ({
  strain: [...new Set([...strainOptions.value, ...miceList.value.map(row => row.strain).filter(Boolean)])],
  gender: [{ value: 'M', label: '♂ 雄' }, { value: 'F', label: '♀ 雌' }, { value: '未知', label: '未知' }],
  parents: [...new Set(miceList.value.map(row => row.parents).filter(Boolean))],
  owner_name: claimerOptions.value.map(claimer => ({ value: claimer.name, label: claimer.name })),
  status: ALL_STATUSES.value,
}))

function gridCellProps(row, field, rowIndex) {
  const select = ['gender', 'owner_name', 'status'].includes(field)
  return {
    value: row[field] || '',
    label: [...mouseInfoColumns, ...noteColumns].find(column => column.field === field)?.label
      || (field === 'owner_name' ? '领取人' : '状态'),
    editorType: field === 'dob' ? 'date' : select ? 'select' : 'text',
    maxLength: field === 'notes' ? 10000 : field === 'claim_purpose' ? 256 : 128,
    options: gridOptions.value[field] || [],
    editable: authStore.isAdmin,
    editOnClick: true,
    clearable: !['gender', 'status'].includes(field),
    disabled: gridSaving.value || loading.value || !!fillDrag.value,
    active: activeCell.value?.id === row.id && activeCell.value?.field === field,
    inFillRange: isInFillRange(field, rowIndex),
  }
}

function gridCellEvents(row, field, rowIndex) {
  return {
    activate: () => activateCell(row.id, field),
    save: value => saveGridValues([row.id], field, value),
    'fill-start': event => startFill(field, rowIndex, event),
    'fill-enter': () => extendFill(field, rowIndex),
  }
}

async function saveGridValues(mouseIds, field, value) {
  if (gridSaving.value || loading.value || !authStore.isAdmin) return
  gridSaving.value = true
  try {
    const result = await miceApi.batchUpdateFields({ mouse_ids: mouseIds, [field]: value || null })
    // Apply server-normalized values and derived age/status without reordering rows.
    const updates = new Map(result.items.map(mouse => [mouse.id, mouse]))
    for (const row of miceList.value) {
      if (updates.has(row.id)) Object.assign(row, updates.get(row.id))
    }
    ElMessage.success(`已保存 ${result.affected_count} 只小鼠的资料`)
    if (['strain', 'parents', 'owner_name', 'status'].includes(field)) await loadOptions()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '小鼠资料保存失败，请重试'))
  } finally {
    gridSaving.value = false
  }
}

function statusPresentation(status) {
  if (status.removes_from_cage) return { type: 'danger', dotClass: 'bg-red-700' }
  switch (status.name) {
    case '已领用': return { type: 'success', dotClass: 'bg-emerald-500' }
    case '在笼': return { type: 'primary', dotClass: 'bg-blue-500' }
    case '繁育中': return { type: 'warning', dotClass: 'bg-amber-500' }
    case '实验中': return { type: 'warning', dotClass: 'bg-orange-500' }
    case '待鉴定': return { type: 'warning', dotClass: 'bg-amber-500' }
    default: return { type: 'info', dotClass: 'bg-gray-400' }
  }
}

function getStatusType(status) {
  return ALL_STATUSES.value.find(item => item.value === status)?.type || 'info'
}

// Batch ear tag detection
const detectedCodes = computed(() => {
  if (!mouseForm.mouse_code) return []
  const parts = mouseForm.mouse_code.split(/[,，\s\n\r]+/).map(s => s.trim()).filter(Boolean)
  return [...new Set(parts)]
})
const detectedCodesCount = computed(() => detectedCodes.value.length)

async function loadOptions() {
  try {
    const [rooms, strains, parents, claimers, statuses] = await Promise.all([
      cagesApi.listRooms(),
      miceApi.getAllStrains(),
      miceApi.getAllParents(),
      claimersApi.listClaimers(),
      mouseStatusesApi.listStatuses()
    ])
    roomOptions.value = rooms
    strainOptions.value = strains
    parentOptions.value = parents
    claimerOptions.value = claimers
    ALL_STATUSES.value = statuses.map(status => ({
      label: status.name,
      value: status.name,
      ...statusPresentation(status)
    }))

  } catch (e) {
    console.error(e)
  }
}

async function handleStatusesChanged() {
  await loadOptions()
  if (filters.status && !ALL_STATUSES.value.some(item => item.value === filters.status)) {
    filters.status = ''
  }
  await loadMice()
}

async function loadMice() {
  cancelFill()
  const requestId = ++loadRequestId
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      keyword: filters.keyword || undefined,
      mouse_code: filters.mouse_code || undefined,
      room: filters.room || undefined,
      cage_code: filters.cage_code || undefined,
      strain: filters.strain || undefined,
      parents: filters.parents.length ? filters.parents.join(',') : undefined,
      gender: filters.gender || undefined,
      owner_name: filters.owner_name || undefined,
      status: filters.status || undefined,
      has_owner: filters.has_owner,
      in_cage: filters.in_cage,
      dob_from: filters.dob_from || undefined,
      dob_to: filters.dob_to || undefined,
      age_weeks_gt: filters.age_weeks_gt ?? undefined,
      age_weeks_lt: filters.age_weeks_lt ?? undefined,
      genotype: filters.genotype || undefined,
      test_status: filters.test_status || undefined,
      claim_purpose: filters.claim_purpose || undefined,
      notes: filters.notes || undefined,
    }
    const res = await miceApi.listMice(params)
    if (requestId !== loadRequestId) return
    miceList.value = res.items
    total.value = res.total
  } catch (e) {
    if (requestId === loadRequestId) ElMessage.error('加载小鼠列表失败')
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadMice()
}

function resetFilters() {
  Object.assign(filters, emptyFilters, { parents: [] })
  handleSearch()
}

function parentOptionLabel(parent) {
  if (/M$/i.test(parent)) return `♂ ${parent.slice(0, -1)}`
  if (/F$/i.test(parent)) return `♀ ${parent.slice(0, -1)}`
  return parent
}

function handleSelectionChange(val) {
  selectedMice.value = val
}

function openSetOwnerDialog(mice) {
  currentOperatingMice.value = mice
  showSetOwnerDialog.value = true
}

function onBatchSuccess() {
  loadMice()
  loadOptions()
}

function viewGenotypes(row) {
  activeMouse.value = row
  showGenotypeDrawer.value = true
}

async function submitBatchTransfer() {
  if (!transferForm.target_room) {
    ElMessage.warning('请选择目标鼠房')
    return
  }
  try {
    const res = await miceApi.batchTransfer({
      mouse_ids: selectedMice.value.map(m => m.id),
      target_room: transferForm.target_room,
      target_cage_code: transferForm.target_cage_code || undefined
    })
    ElMessage.success(res.message)
    showTransferDialog.value = false
    loadMice()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '转移失败')
  }
}

async function handleBatchStatus(status) {
  try {
    const res = await miceApi.batchUpdateStatus({
      mouse_ids: selectedMice.value.map(m => m.id),
      status: status
    })
    ElMessage.success(res.message)
    loadMice()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

function openAddMouseDialog() {
  Object.assign(mouseForm, {
    add_count: 1,
    start_code: '',
    mouse_code: '',
    strain: '',
    gender: 'M',
    dob: '',
    parents: '',
    genotype_1: '',
    source_room: roomOptions.value[0] || '',
    cage_code: '',
    status: '在笼',
    owner_name: '',
    notes: ''
  })
  parentsDetection.value = null
  showAddMouseDialog.value = true
}

function updateMouseCodes() {
  mouseForm.mouse_code = generateSequentialMouseCodes(mouseForm.start_code, mouseForm.add_count).join(', ')
}

function openEditDialog(row) {
  detailMouseCode.value = row.mouse_code || ''
  detailMouseId.value = row.id || null
  detailStartInEditMode.value = true
  showMouseDetailModal.value = true
}

// Smart Parents Pedigree Detection
const parentsDetection = ref(null)
let parseParentsTimer = null

watch(() => mouseForm.parents, (val) => {
  if (parseParentsTimer) clearTimeout(parseParentsTimer)
  if (!val || !val.trim() || ['新品系引入', '外购', '无', '不明', '不详', '/', '-'].includes(val.trim())) {
    parentsDetection.value = null
    return
  }
  parseParentsTimer = setTimeout(async () => {
    try {
      const res = await miceApi.parseParents(val)
      parentsDetection.value = res
    } catch (e) {
      parentsDetection.value = null
    }
  }, 250)
})

function handleParentsBlur() {
  if (parentsDetection.value?.normalized && parentsDetection.value.has_changes) {
    mouseForm.parents = parentsDetection.value.normalized
  }
}

async function submitAddMouseForm() {
  try {
    if (parentsDetection.value?.normalized && parentsDetection.value.has_changes) {
      mouseForm.parents = parentsDetection.value.normalized
    }
    const codes = detectedCodes.value
    if (codes.length > 1) {
      const res = await miceApi.batchCreateMice({
        mouse_codes: codes,
        strain: mouseForm.strain,
        gender: mouseForm.gender,
        dob: mouseForm.dob || undefined,
        parents: mouseForm.parents || undefined,
        genotype_1: mouseForm.genotype_1 || undefined,
        source_room: mouseForm.source_room || undefined,
        owner_name: mouseForm.owner_name || undefined,
        status: mouseForm.status || '在笼',
        notes: mouseForm.notes || undefined
      })
      ElMessage.success(res.message || `成功批量录入 ${codes.length} 只小鼠`)
    } else {
      const singleCode = codes[0] || mouseForm.mouse_code.trim()
      if (!singleCode) {
        ElMessage.warning('请输入小鼠耳标编号')
        return
      }
      const { add_count, start_code, ...mouseData } = mouseForm
      const res = await miceApi.createMouse({ ...mouseData, mouse_code: singleCode })
      ElMessage.success(res.message || (res.mouse_code !== singleCode
        ? `耳标编号 [${singleCode}] 已存在，已自动更名为 [${res.mouse_code}]`
        : '小鼠已成功录入'))
    }
    showAddMouseDialog.value = false
    handleSearch()
    loadOptions()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function handleDeleteMouse(id) {
  try {
    await miceApi.deleteMouse(id)
    ElMessage.success('删除成功')
    loadMice()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    await importExportApi.exportMice()
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  if (route.query.owner_name) {
    filters.owner_name = route.query.owner_name
  }
  fetchClaimerColors()
  loadOptions()
  loadMice()
})
</script>

<style scoped>
.mouse-search-bar { max-width: 420px; }

.parent-reference:hover {
  box-shadow: 0 0 0 2px #d8b4fe;
  transform: translateY(-1px);
}
</style>

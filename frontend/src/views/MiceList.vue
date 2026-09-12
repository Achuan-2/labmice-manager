<template>
  <div class="mice-page">
    <!-- Filter Bar -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-4">
      <div class="mouse-filter-grid grid gap-3 mb-3 items-start">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索耳标、品系、基因型或备注"
          clearable
          prefix-icon="Search"
          @keyup.enter="handleSearch"
        />

        <el-select v-model="filters.room" clearable placeholder="全部鼠房" @change="handleSearch">
          <el-option v-for="r in roomOptions" :key="r" :label="r" :value="r" />
        </el-select>

        <el-select v-model="filters.strain" clearable filterable placeholder="全部品系" @change="handleSearch">
          <el-option v-for="s in strainOptions" :key="s" :label="s" :value="s" />
        </el-select>

        <el-select
          v-model="filters.parents"
          multiple
          clearable
          filterable
          :reserve-keyword="false"
          placeholder="按父母筛选"
          @change="handleSearch"
        >
          <el-option v-for="parent in parentOptions" :key="parent" :label="parentOptionLabel(parent)" :value="parent" />
        </el-select>

        <el-select v-model="filters.gender" clearable placeholder="全部性别" @change="handleSearch">
          <el-option label="雄性 (M)" value="M" />
          <el-option label="雌性 (F)" value="F" />
        </el-select>

        <el-select v-model="filters.status" clearable placeholder="全部状态" @change="handleSearch">
          <el-option v-for="st in ALL_STATUSES" :key="st.value" :label="st.label" :value="st.value" />
        </el-select>

        <el-select v-model="filters.owner_name" clearable filterable placeholder="按领取人筛选" @change="handleSearch">
          <el-option v-for="c in claimerOptions" :key="c.name" :label="c.name" :value="c.name" />
        </el-select>
      </div>

      <div class="flex items-center justify-between pt-2 border-t border-gray-100">
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-500 font-medium">快捷筛选:</span>
          <el-radio-group v-model="quickFilter" size="small" @change="handleQuickFilter">
            <el-radio-button value="all">全部小鼠</el-radio-button>
            <el-radio-button value="unclaimed">仅未领用 (待分配)</el-radio-button>
            <el-radio-button value="claimed">仅已领用</el-radio-button>
            <el-radio-button value="in_cage">当前在笼</el-radio-button>
          </el-radio-group>
        </div>

        <div class="flex items-center gap-2">
          <el-button @click="resetFilters" size="small">重置筛选</el-button>
          <el-button type="primary" size="small" @click="handleSearch">查询</el-button>
        </div>
      </div>
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
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <el-table
        v-loading="loading"
        :data="miceList"
        row-key="id"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />

        <el-table-column prop="mouse_code" label="耳标 / 编号" width="140" fixed>
          <template #default="{ row }">
            <div
              class="inline-flex items-center cursor-pointer text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded transition-colors group"
              title="点击查看小鼠完整档案、系谱及流转记录"
              @click="openMouseDetail(row)"
            >
              <span class="font-bold font-mono text-sm underline-offset-2 group-hover:underline">
                {{ row.mouse_code }}
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="strain" label="品系 / 基因型" min-width="140">
          <template #default="{ row }">
            <div
              v-if="row.strain"
              class="inline-flex items-center gap-1 cursor-pointer text-blue-700 hover:text-blue-900 group"
              title="点击查看并填写该品系背景说明与小鼠备注"
              @click="openStrainNotesDialog(row)"
            >
              <span class="font-semibold underline-offset-2 group-hover:underline">{{ row.strain }}</span>
              <span v-if="strainNotesMap[row.strain]" class="text-[11px]" title="已填品系全局备注">📝</span>
            </div>
            <span v-else class="text-gray-300">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="gender" label="性别" width="80">
          <template #default="{ row }">
            <el-tag
              v-if="row.gender === 'M'"
              size="small"
              type="primary"
              effect="light"
            >
              ♂ 雄
            </el-tag>
            <el-tag
              v-else-if="row.gender === 'F'"
              size="small"
              type="danger"
              effect="light"
            >
              ♀ 雌
            </el-tag>
            <el-tag v-else size="small" type="info">未知</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="出生日期 / 周龄" width="160">
          <template #default="{ row }">
            <div class="text-xs">
              <span class="text-gray-700 font-mono">{{ row.dob || '-' }}</span>
              <span v-if="row.age_weeks !== null" class="ml-1.5 font-bold text-emerald-600">
                ({{ row.age_weeks }} 周)
              </span>
            </div>
          </template>
        </el-table-column>

        <!-- 父母系谱 Column -->
        <el-table-column prop="parents" label="父母系谱 (M+F)" min-width="170">
          <template #default="{ row }">
            <PedigreeTags :parents="row.parents" @click-parent="openMouseDetail" />
          </template>
        </el-table-column>

        <!-- Direct Genotype Linkage Column -->
        <el-table-column label="基因鉴定结果" min-width="150">
          <template #default="{ row }">
            <div v-if="row.genotypes && row.genotypes.length > 0" class="flex items-center gap-1">
              <el-tag
                size="small"
                type="success"
                effect="plain"
                class="cursor-pointer hover:opacity-80"
                @click="viewGenotypes(row)"
              >
                🔬 {{ row.genotypes[0].genotype_1 || '已鉴定' }}
                <span v-if="row.genotypes.length > 1" class="text-xs ml-0.5">({{ row.genotypes.length }})</span>
              </el-tag>
            </div>
            <div v-else-if="row.genotype_1">
              <el-tag size="small" type="info">{{ row.genotype_1 }}</el-tag>
            </div>
            <div v-else class="text-xs text-gray-300">未鉴定</div>
          </template>
        </el-table-column>

        <el-table-column label="当前笼位与鼠房" min-width="160">
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
        <el-table-column label="当前领取人" width="140">
          <template #default="{ row }">
            <div v-if="row.owner_name" class="flex items-center gap-1">
              <el-tag
                size="small"
                :style="getClaimerTagStyle(row.owner_name)"
                class="font-medium border"
              >
                👤 {{ row.owner_name }}
              </el-tag>
            </div>
            <div v-else>
              <el-tag size="small" type="info" effect="plain" class="text-gray-400">未分配</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="getStatusType(row.status)"
            >
              {{ mouseStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="claim_purpose" label="领用用途 / 备注" min-width="160">
          <template #default="{ row }">
            <div class="text-xs text-gray-600 truncate" :title="row.claim_purpose || row.notes">
              <span v-if="row.claim_purpose" class="text-blue-600 font-medium">[{{ row.claim_purpose }}] </span>
              {{ row.notes || '' }}
            </div>
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
            <el-tag size="small" type="success">{{ gt.genotype_1 || '阳性' }}</el-tag>
          </div>
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

    <!-- Strain & Mouse Notes Dialog -->
    <el-dialog v-model="showStrainNotesDialog" title="品系档案与备注设置" width="500px">
      <div v-if="currentSelectedStrain" class="space-y-4 text-xs">
        <div class="bg-blue-50/70 border border-blue-100 rounded-lg p-3 flex justify-between items-center">
          <div>
            <span class="text-gray-500">品系名称:</span>
            <span class="ml-2 font-bold text-sm text-blue-800 font-mono">{{ currentSelectedStrain }}</span>
          </div>
          <el-tag size="small" type="primary">在库小鼠: {{ currentStrainMouseCount }} 只</el-tag>
        </div>

        <div>
          <div class="font-semibold text-gray-700 mb-1 flex items-center justify-between">
            <span>🧬 品系全局背景 / 繁育与鉴定说明 (对所有该品系小鼠通用)</span>
          </div>
          <el-input
            v-model="strainNotesForm.strain_notes"
            type="textarea"
            :rows="3"
            placeholder="如: 该品系由集萃引入，需与C57交配扩繁，基因鉴定使用Primer 12号..."
          />
        </div>

        <div v-if="currentStrainTargetMouse" class="border-t border-gray-100 pt-3">
          <div class="font-semibold text-gray-700 mb-1 flex items-center justify-between">
            <span>🐁 当前小鼠专属备注 [{{ currentStrainTargetMouse.mouse_code }}]</span>
          </div>
          <el-input
            v-model="strainNotesForm.mouse_notes"
            type="textarea"
            :rows="2"
            placeholder="本只小鼠的单独领用或实验备注..."
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="showStrainNotesDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingStrainNotes" @click="saveStrainNotes">保存备注</el-button>
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
import { miceApi, cagesApi, claimersApi, strainsApi, mouseStatusesApi, importExportApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClaimerColors } from '@/composables/useClaimerColors'
import SetOwnerDialog from '@/components/SetOwnerDialog.vue'
import MouseDetailModal from '@/components/MouseDetailModal.vue'
import MouseStatusManager from '@/components/MouseStatusManager.vue'
import CageDetailDialog from '@/components/CageDetailDialog.vue'
import { isClaimedOutOfCage, mouseStatusLabel } from '@/utils/mouseDisplay'
import { generateSequentialMouseCodes } from '@/utils/mouseCodes'
import PedigreeTags from '@/components/PedigreeTags.vue'
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

const roomOptions = ref([])
const strainOptions = ref([])
const parentOptions = ref([])
const claimerOptions = ref([])
const quickFilter = ref('all')

const filters = reactive({
  keyword: '',
  room: '',
  strain: '',
  parents: [],
  gender: '',
  owner_name: '',
  status: '',
  has_owner: null
})

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

function statusPresentation(status) {
  if (status.removes_from_cage) return { type: 'danger', dotClass: 'bg-red-700' }
  switch (status.name) {
    case '已领用': return { type: 'success', dotClass: 'bg-emerald-500' }
    case '在笼': return { type: 'primary', dotClass: 'bg-blue-500' }
    case '繁育中': return { type: 'warning', dotClass: 'bg-amber-500' }
    case '实验中': return { type: 'warning', dotClass: 'bg-orange-500' }
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

// Strain Notes Dialog State & Methods
const showStrainNotesDialog = ref(false)
const currentSelectedStrain = ref('')
const currentStrainTargetMouse = ref(null)
const currentStrainMouseCount = ref(0)
const savingStrainNotes = ref(false)
const strainNotesMap = ref({})

const strainNotesForm = reactive({
  strain_notes: '',
  mouse_notes: ''
})

async function openStrainNotesDialog(row) {
  if (!row?.strain) return
  currentSelectedStrain.value = row.strain
  currentStrainTargetMouse.value = row
  strainNotesForm.mouse_notes = row.notes || ''
  strainNotesForm.strain_notes = strainNotesMap.value[row.strain] || ''

  showStrainNotesDialog.value = true

  try {
    const detail = await strainsApi.getStrain(row.strain)
    strainNotesForm.strain_notes = detail.notes || ''
    currentStrainMouseCount.value = detail.mouse_count || 0
  } catch (e) {
    console.error(e)
  }
}

async function saveStrainNotes() {
  if (!currentSelectedStrain.value) return
  savingStrainNotes.value = true
  try {
    await strainsApi.updateStrainNotes(currentSelectedStrain.value, strainNotesForm.strain_notes)
    strainNotesMap.value[currentSelectedStrain.value] = strainNotesForm.strain_notes

    if (currentStrainTargetMouse.value?.id && strainNotesForm.mouse_notes !== currentStrainTargetMouse.value.notes) {
      await miceApi.updateMouse(currentStrainTargetMouse.value.id, {
        notes: strainNotesForm.mouse_notes
      })
      currentStrainTargetMouse.value.notes = strainNotesForm.mouse_notes
    }

    ElMessage.success('品系及小鼠备注保存成功')
    showStrainNotesDialog.value = false
    loadMice()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存备注失败')
  } finally {
    savingStrainNotes.value = false
  }
}

async function loadOptions() {
  try {
    const [rooms, strains, parents, claimers, strainList, statuses] = await Promise.all([
      cagesApi.listRooms(),
      miceApi.getAllStrains(),
      miceApi.getAllParents(),
      claimersApi.listClaimers(),
      strainsApi.listStrains(),
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

    const map = {}
    if (Array.isArray(strainList)) {
      strainList.forEach(s => {
        if (s.notes) map[s.name] = s.notes
      })
    }
    strainNotesMap.value = map
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
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      room: filters.room || undefined,
      strain: filters.strain || undefined,
      parents: filters.parents.length ? filters.parents.join(',') : undefined,
      gender: filters.gender || undefined,
      owner_name: filters.owner_name || undefined,
      status: filters.status || undefined,
      has_owner: filters.has_owner
    }
    const res = await miceApi.listMice(params)
    miceList.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error('加载小鼠列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadMice()
}

function resetFilters() {
  filters.keyword = ''
  filters.room = ''
  filters.strain = ''
  filters.parents = []
  filters.gender = ''
  filters.owner_name = ''
  filters.status = ''
  filters.has_owner = null
  quickFilter.value = 'all'
  handleSearch()
}

function parentOptionLabel(parent) {
  if (/M$/i.test(parent)) return `♂ ${parent.slice(0, -1)}`
  if (/F$/i.test(parent)) return `♀ ${parent.slice(0, -1)}`
  return parent
}

function handleQuickFilter(val) {
  if (val === 'unclaimed') {
    filters.has_owner = false
    filters.status = ''
  } else if (val === 'claimed') {
    filters.has_owner = true
    filters.status = ''
  } else if (val === 'in_cage') {
    filters.has_owner = null
    filters.status = '在笼'
  } else {
    filters.has_owner = null
    filters.status = ''
  }
  handleSearch()
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
    loadMice()
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
.mouse-filter-grid {
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  align-items: start;
}

.mouse-filter-grid :deep(.el-input) {
  height: 32px;
}

.parent-reference:hover {
  box-shadow: 0 0 0 2px #d8b4fe;
  transform: translateY(-1px);
}
</style>

<template>
  <div
    class="win-th-container"
    :class="[
      `align-${align}`,
      { 'is-active': isCurrentProp }
    ]"
    :title="tooltipText"
    @click="handleHeaderClick"
  >
    <span class="win-th-label">{{ label }}</span>

    <!-- 仅当前排序列才显示升序/降序符号（未排序列完全不显示任何符号） -->
    <span v-if="isCurrentProp && (activeOrder === 'asc' || activeOrder === 'desc')" class="win-sort-indicator">
      <span v-if="activeOrder === 'asc'" class="win-arrow win-arrow-asc">▲</span>
      <span v-else-if="activeOrder === 'desc'" class="win-arrow win-arrow-desc">▼</span>
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  prop: { type: String, required: true },
  label: { type: String, required: true },
  ascText: { type: String, default: '从小到大' },
  descText: { type: String, default: '从大到小' },
  activeProp: { type: String, default: '' },
  activeOrder: { type: String, default: '' }, // 'asc' | 'desc' | ''
  align: { type: String, default: 'left' }
})

const emit = defineEmits(['sort', 'clear'])

const isCurrentProp = computed(() => props.activeProp === props.prop)

const tooltipText = computed(() => {
  if (!isCurrentProp.value) {
    return `点击按【${props.label}】排序 (${props.ascText})`
  }
  if (props.activeOrder === 'asc') {
    return `当前为升序，点击切换为降序 (${props.descText})`
  }
  if (props.activeOrder === 'desc') {
    return `当前为降序，点击恢复默认顺序`
  }
  return `点击对【${props.label}】排序`
})

function handleHeaderClick() {
  if (!isCurrentProp.value) {
    // 首次点击：升序
    emit('sort', props.prop, 'asc')
  } else if (props.activeOrder === 'asc') {
    // 再次点击：降序
    emit('sort', props.prop, 'desc')
  } else {
    // 第三次点击：恢复默认
    emit('clear')
  }
}
</script>

<style scoped>
.win-th-container {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.15s ease-in-out;
  vertical-align: middle;
  white-space: nowrap;
}

.win-th-container.align-center {
  justify-content: center;
}

.win-th-container.align-right {
  justify-content: flex-end;
}

.win-th-container:hover {
  background-color: #f1f5f9;
}

.win-th-container.is-active {
  background-color: #eff6ff;
}

.win-th-label {
  font-weight: 600;
  font-size: 13px;
  color: #374151;
  transition: color 0.15s ease;
}

.win-th-container:hover .win-th-label {
  color: #1d4ed8;
}

.win-th-container.is-active .win-th-label {
  color: #1d4ed8;
  font-weight: 700;
}

.win-sort-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 13px;
  height: 13px;
  line-height: 1;
}

.win-arrow {
  font-size: 10px;
  line-height: 1;
  font-weight: bold;
  transition: all 0.15s ease;
}

.win-arrow-asc,
.win-arrow-desc {
  color: #2563eb;
  transform: scale(1.1);
}
</style>

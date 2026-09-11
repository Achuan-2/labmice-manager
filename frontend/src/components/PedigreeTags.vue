<template>
  <div class="pedigree-tags-container inline-flex flex-wrap items-center gap-1">
    <!-- Empty / Unknown -->
    <span v-if="!parents || parents === '-' || parents === '/' || parents === '不详' || parents === '不明'" class="text-gray-300 text-xs">
      -
    </span>

    <!-- Special Source Note (e.g. 新品系引入) -->
    <el-tag
      v-else-if="specialNote"
      size="small"
      type="info"
      effect="plain"
      class="text-[11px]"
    >
      {{ specialNote }}
    </el-tag>

    <!-- Parsed Parent Mice Badges -->
    <template v-else-if="parsedList.length > 0">
      <el-tag
        v-for="p in parsedList"
        :key="p.code"
        size="small"
        :type="p.gender === 'M' ? 'primary' : (p.gender === 'F' ? 'danger' : 'info')"
        :effect="p.gender ? 'light' : 'plain'"
        class="cursor-pointer transition-all hover:scale-105 font-mono select-none"
        :class="p.gender === 'M' ? 'hover:border-blue-500' : 'hover:border-pink-500'"
        :title="`点击查看${p.gender === 'M' ? '父本 ♂' : (p.gender === 'F' ? '母本 ♀' : '亲本')} [${p.code}] 的完整档案与系谱`"
        @click.stop="handleClick(p.code)"
      >
        <span class="font-bold">{{ p.gender === 'M' ? '♂' : (p.gender === 'F' ? '♀' : '') }}</span>
        <span class="ml-0.5">{{ p.code }}</span>
      </el-tag>
    </template>

    <!-- Fallback raw text string -->
    <span
      v-else
      class="font-mono text-xs text-purple-800 font-bold bg-purple-50 px-2 py-0.5 rounded border border-purple-200/80 inline-block truncate max-w-[180px]"
      :title="parents"
    >
      {{ parents }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  parents: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['clickParent'])

const specialNote = computed(() => {
  if (!props.parents) return null
  const p = props.parents.trim()
  if (p.includes('新品系') || p.includes('集萃') || p.includes('邓娟组') || p.includes('外购') || p.includes('引入')) {
    return p
  }
  return null
})

const parsedList = computed(() => {
  if (specialNote.value) return []
  if (!props.parents) return []
  const text = props.parents.trim()
  if (!text || text === '/' || text === '-' || text === '不明' || text === '不详') return []

  const cleaned = text.replace(/[\(（].*?[\)）]/g, '')
  const parts = cleaned.split(/[+、/,，\s\\]+/)
  const results = []

  for (const part of parts) {
    const p = part.trim()
    if (!p || p === '/' || p === '无' || p.includes('无耳标')) continue

    // Code with gender suffix (e.g. E925M, E822F, 111F)
    const mfMatch = p.match(/^([A-Za-z0-9_-]+?)([MFmf])$/)
    if (mfMatch) {
      const code = mfMatch[1].trim()
      const gender = mfMatch[2].toUpperCase()
      if (!['HO', 'KO', 'CAS', 'GF', 'BF', 'WT'].includes(code.toUpperCase())) {
        results.push({
          code,
          gender
        })
        continue
      }
    }

    // Alphanumeric tag (e.g. B8, 318, 503)
    if (/^[A-Za-z0-9_-]{2,10}$/.test(p) && !/^[A-Za-z]+$/.test(p)) {
      results.push({
        code: p,
        gender: null
      })
    }
  }

  return results
})

function handleClick(code) {
  emit('clickParent', code)
}
</script>

<style scoped>
.pedigree-tags-container {
  vertical-align: middle;
}
</style>

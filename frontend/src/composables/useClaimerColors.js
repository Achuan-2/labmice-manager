import { ref } from 'vue'
import { claimersApi } from '@/api'

export const PRESET_COLORS = [
  '#2563eb', // 宝石蓝
  '#059669', // 翠绿
  '#d97706', // 琥珀橙
  '#7c3aed', // 罗兰紫
  '#db2777', // 玫红
  '#0891b2', // 青绿
  '#ea580c', // 烈焰橙
  '#4f46e5', // 靛青
  '#16a34a', // 鲜绿
  '#c026d3', // 兰花紫
  '#e11d48', // 胭脂红
  '#0d9488', // 蓝绿
  '#6366f1', // 丁香紫
  '#b45309', // 棕黄
  '#0284c7', // 天蓝
  '#be185d'  // 樱桃红
]

// Global reactive cache shared across views
const claimerColorMap = ref({})
let isFetching = false

function hashString(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

export function useClaimerColors() {
  async function fetchClaimerColors() {
    if (isFetching) return
    isFetching = true
    try {
      const list = await claimersApi.listClaimers()
      const map = {}
      for (const c of list) {
        if (c.name) {
          map[c.name] = c.color || PRESET_COLORS[hashString(c.name) % PRESET_COLORS.length]
        }
      }
      claimerColorMap.value = map
    } catch (e) {
      console.warn('Failed to fetch claimer colors', e)
    } finally {
      isFetching = false
    }
  }

  function getClaimerColor(name) {
    if (!name || typeof name !== 'string') return '#6b7280'
    const clean = name.trim()
    if (!clean) return '#6b7280'
    if (claimerColorMap.value[clean]) {
      return claimerColorMap.value[clean]
    }
    // Deterministic fallback from palette based on name hash
    return PRESET_COLORS[hashString(clean) % PRESET_COLORS.length]
  }

  function getClaimerTagStyle(name) {
    if (!name) return {}
    const color = getClaimerColor(name)
    return {
      backgroundColor: `${color}18`,
      color: color,
      borderColor: `${color}45`,
      fontWeight: '600'
    }
  }

  function getClaimerAvatarStyle(name, customColor = null) {
    const color = customColor || getClaimerColor(name)
    return {
      backgroundColor: `${color}18`,
      color: color,
      borderColor: `${color}60`
    }
  }

  return {
    claimerColorMap,
    fetchClaimerColors,
    getClaimerColor,
    getClaimerTagStyle,
    getClaimerAvatarStyle,
    PRESET_COLORS
  }
}

export const useMemberColors = useClaimerColors

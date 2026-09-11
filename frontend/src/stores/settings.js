import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { settingsApi } from '@/api'

const DEFAULT_GROUP_NAME = '课题组'

export const useSettingsStore = defineStore('settings', () => {
  const groupName = ref(DEFAULT_GROUP_NAME)
  const loaded = ref(false)
  const systemName = computed(() => `${groupName.value}小鼠管理系统`)

  function applySettings(settings) {
    groupName.value = settings?.group_name?.trim() || DEFAULT_GROUP_NAME
    document.title = systemName.value
  }

  async function load() {
    try {
      applySettings(await settingsApi.getPublic())
    } catch {
      applySettings(null)
    } finally {
      loaded.value = true
    }
  }

  async function update(groupNameValue) {
    const settings = await settingsApi.update({ group_name: groupNameValue })
    applySettings(settings)
    return settings
  }

  return { groupName, systemName, loaded, load, update }
})

import { ref } from 'vue'
import { defineStore } from 'pinia'
import { settingsApi } from '@/api'

const DEFAULT_SYSTEM_NAME = '课题组小鼠管理系统'

export const useSettingsStore = defineStore('settings', () => {
  const systemName = ref(DEFAULT_SYSTEM_NAME)
  const loaded = ref(false)

  function applySettings(settings) {
    systemName.value = settings?.system_name?.trim() || DEFAULT_SYSTEM_NAME
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

  async function update(systemNameValue) {
    const settings = await settingsApi.update({ system_name: systemNameValue })
    applySettings(settings)
    return settings
  }

  return { systemName, loaded, load, update }
})

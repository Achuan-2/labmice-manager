<template>
  <template v-for="dialog in dialogs" :key="dialog.id">
    <MouseDetailModal
      v-if="dialog.type === 'mouse'"
      v-model="dialog.visible"
      :mouse-id="dialog.mouseId"
      :mouse-code="dialog.mouseCode"
      @closed="closeDialog(dialog.id)"
      @refresh="dialog.onRefresh?.()"
      @set-owner="openOwnerDialog(dialog, $event)"
    />
    <CageRack
      v-else-if="dialog.type === 'cage'"
      :dialog-only="true"
      :initial-cage-id="dialog.cageId"
      @closed="closeDialog(dialog.id)"
      @refresh="dialog.onRefresh?.()"
    />
    <SetOwnerDialog
      v-else-if="dialog.type === 'owner'"
      v-model="dialog.visible"
      :mice="dialog.mice"
      @update:model-value="open => { if (!open) closeDialog(dialog.id) }"
      @success="dialog.onRefresh?.()"
    />
  </template>
</template>

<script setup>
import { defineAsyncComponent, onUnmounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useArchiveDialogs } from '@/composables/useArchiveDialogs'
import SetOwnerDialog from './SetOwnerDialog.vue'

// Load independently so nested mouse/cage links can open another instance.
const MouseDetailModal = defineAsyncComponent(() => import('./MouseDetailModal.vue'))
const CageRack = defineAsyncComponent(() => import('@/views/CageRack.vue'))
const { dialogs, openOwner, closeDialog, clearDialogs } = useArchiveDialogs()
const authStore = useAuthStore()

function openOwnerDialog(source, mouse) {
  openOwner(mouse, source.onRefresh)
}

watch(() => authStore.isAuthenticated, authenticated => {
  if (!authenticated) clearDialogs()
})
onUnmounted(clearDialogs)
</script>

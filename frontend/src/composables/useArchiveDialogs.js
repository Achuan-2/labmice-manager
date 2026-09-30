import { nextTick, reactive } from 'vue'

// Keep each opened archive/editor instance independent of the page and other dialogs.
const dialogs = reactive([])
let nextDialogId = 0

function openDialog(type, data, onRefresh) {
  const dialog = { id: ++nextDialogId, type, ...data, visible: false, onRefresh }
  dialogs.push(dialog)
  // Mount first, then open so existing dialog watchers load their initial data.
  nextTick(() => {
    const mounted = dialogs.find(item => item.id === dialog.id)
    if (mounted) mounted.visible = true
  })
}

export function useArchiveDialogs() {
  return {
    dialogs,
    openMouse(mouse, onRefresh) {
      if (!mouse?.id && !mouse?.mouse_code) return
      openDialog('mouse', { mouseId: mouse.id || null, mouseCode: mouse.mouse_code || '' }, onRefresh)
    },
    openCageEditor(cageId, onRefresh) {
      if (cageId) openDialog('cage', { cageId }, onRefresh)
    },
    openOwner(mouse, onRefresh) {
      if (mouse) openDialog('owner', { mice: [mouse] }, onRefresh)
    },
    closeDialog(id) {
      const index = dialogs.findIndex(dialog => dialog.id === id)
      if (index !== -1) dialogs.splice(index, 1)
    },
    clearDialogs() {
      dialogs.splice(0)
    }
  }
}

import { onBeforeUnmount, ref, watch } from 'vue'

// Fill only the visible rows. Save a whole range through one atomic request.
export function useGridFill(rows, isDisabled, saveValues) {
  const activeCell = ref(null)
  const fillDrag = ref(null)

  function activateCell(id, field) {
    if (!isDisabled() && !fillDrag.value) activeCell.value = { id, field }
  }

  function startFill(field, rowIndex, event) {
    if (event.button !== 0 || isDisabled()) return
    cancelFill()
    const row = rows.value[rowIndex]
    if (!row) return
    activeCell.value = { id: row.id, field }
    fillDrag.value = {
      field, sourceId: row.id, startIndex: rowIndex, endIndex: rowIndex,
      value: row[field] || '', previousUserSelect: document.body.style.userSelect,
    }
    document.body.style.userSelect = 'none'
    document.addEventListener('pointerup', finishFill)
    document.addEventListener('pointercancel', cancelFill)
    document.addEventListener('keydown', handleKeydown)
  }

  function extendFill(field, rowIndex) {
    if (fillDrag.value?.field === field) fillDrag.value.endIndex = rowIndex
  }

  function isInFillRange(field, rowIndex) {
    const drag = fillDrag.value
    return drag?.field === field && rowIndex >= Math.min(drag.startIndex, drag.endIndex)
      && rowIndex <= Math.max(drag.startIndex, drag.endIndex)
  }

  function finishFill() {
    const drag = fillDrag.value
    if (!drag) return
    const ids = rows.value
      .slice(Math.min(drag.startIndex, drag.endIndex), Math.max(drag.startIndex, drag.endIndex) + 1)
      .filter(row => row.id !== drag.sourceId)
      .map(row => row.id)
    cancelFill()
    if (ids.length) saveValues(ids, drag.field, drag.value)
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') cancelFill()
  }

  function cancelFill() {
    if (fillDrag.value) document.body.style.userSelect = fillDrag.value.previousUserSelect
    fillDrag.value = null
    document.removeEventListener('pointerup', finishFill)
    document.removeEventListener('pointercancel', cancelFill)
    document.removeEventListener('keydown', handleKeydown)
  }

  watch(rows, () => {
    cancelFill()
    activeCell.value = null
  })
  onBeforeUnmount(cancelFill)

  return { activeCell, fillDrag, activateCell, startFill, extendFill, isInFillRange, cancelFill }
}

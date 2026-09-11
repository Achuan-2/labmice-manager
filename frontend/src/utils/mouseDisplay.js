export function isClaimedOutOfCage(mouse) {
  return Boolean(mouse && !mouse.cage_id && !mouse.cage_code)
}

export function mouseStatusLabel(mouse) {
  return mouse?.status || (isClaimedOutOfCage(mouse) ? '出笼' : '在笼')
}

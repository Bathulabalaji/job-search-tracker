import type { KeyboardCoordinateGetter } from "@dnd-kit/core"

/**
 * Left/right arrows jump a picked-up card to the neighbouring column
 * (the default 25px steps would take ~12 presses per column).
 */
export const columnCoordinateGetter: KeyboardCoordinateGetter = (
  event,
  { context: { active, droppableRects, droppableContainers, collisionRect } },
) => {
  if (!active || !collisionRect) return undefined
  if (event.code !== "ArrowRight" && event.code !== "ArrowLeft") return undefined
  event.preventDefault()

  const columns = droppableContainers
    .getEnabled()
    .map((container) => ({ id: container.id, rect: droppableRects.get(container.id) }))
    .flatMap((entry) => (entry.rect ? [{ id: entry.id, rect: entry.rect }] : []))
    .sort((a, b) => a.rect.left - b.rect.left)

  const centerX = collisionRect.left + collisionRect.width / 2
  const currentIndex = columns.findIndex(
    (column) => centerX >= column.rect.left && centerX <= column.rect.left + column.rect.width,
  )
  const step = event.code === "ArrowRight" ? 1 : -1
  const target = columns[Math.min(Math.max(currentIndex + step, 0), columns.length - 1)]
  if (!target) return undefined

  return {
    x: target.rect.left + (target.rect.width - collisionRect.width) / 2,
    y: target.rect.top + 56,
  }
}

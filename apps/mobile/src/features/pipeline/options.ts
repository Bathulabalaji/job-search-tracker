import type { Option } from "@/components/ui/option-sheet"
import { STAGES, SOURCES, type Source, type Stage } from "@/api/types"
import { PRIORITY_LABELS, STAGE_LABELS, titleCase } from "@/lib/format"

export const STAGE_OPTIONS: Option<Stage>[] = STAGES.map((s) => ({
  value: s,
  label: STAGE_LABELS[s],
}))

export const SOURCE_OPTIONS: Option<Source>[] = SOURCES.map((s) => ({
  value: s,
  label: titleCase(s),
}))

export const PRIORITY_OPTIONS: Option<number>[] = [1, 2, 3].map((p) => ({
  value: p,
  label: PRIORITY_LABELS[p] ?? String(p),
}))

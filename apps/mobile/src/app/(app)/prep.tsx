import { useMemo, useState } from "react"
import { Pressable, View } from "react-native"

import { usePrepItems, useUpdatePrepItem } from "@/api/prep-items"
import { PREP_CATEGORIES, type PrepCategory, type PrepItem, type PrepStatus } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Chip, ChipRow } from "@/components/ui/chip"
import { Icon, type IconName } from "@/components/ui/icon"
import { ProgressBar } from "@/components/ui/progress"
import { Screen } from "@/components/ui/screen"
import { SkeletonList } from "@/components/ui/skeleton"
import { EmptyState, ErrorState } from "@/components/ui/states"
import { Text } from "@/components/ui/text"
import { CATEGORY_LABELS } from "@/features/prep/categories"
import { PrepSheet } from "@/features/prep/prep-sheet"
import { haptics } from "@/lib/haptics"
import { space } from "@/theme/tokens"

const NEXT_STATUS: Record<PrepStatus, PrepStatus> = { todo: "doing", doing: "done", done: "todo" }
const STATUS_ICON: Record<PrepStatus, IconName> = {
  todo: "ellipse-outline",
  doing: "contrast-outline",
  done: "checkmark-circle",
}

function Stars({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <View accessibilityLabel={`Confidence ${value} of 5`} style={{ flexDirection: "row" }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Pressable
          key={n}
          accessibilityRole="button"
          accessibilityLabel={`Set confidence to ${n}`}
          hitSlop={{ top: 8, bottom: 8 }}
          onPress={() => {
            haptics.tap()
            onChange(n)
          }}
          style={{ padding: 3 }}
        >
          <Icon name={n <= value ? "star" : "star-outline"} size={20} color={n <= value ? "warning" : "muted"} />
        </Pressable>
      ))}
    </View>
  )
}

export default function PrepScreen() {
  const { data, isPending, isError, error, refetch, isRefetching } = usePrepItems()
  const update = useUpdatePrepItem()
  const [category, setCategory] = useState<PrepCategory | "all">("all")
  const [sheet, setSheet] = useState<{ open: boolean; item: PrepItem | null }>({ open: false, item: null })

  const stats = useMemo(() => {
    const items = data ?? []
    const done = items.filter((i) => i.status === "done").length
    return { total: items.length, done, percent: items.length ? (done / items.length) * 100 : 0 }
  }, [data])

  const visible = useMemo(
    () => (data ?? []).filter((i) => category === "all" || i.category === category),
    [data, category],
  )

  return (
    <Screen edges={[]} refreshing={isRefetching && !isPending} onRefresh={() => void refetch()} contentStyle={{ paddingHorizontal: 0 }}>
      <View style={{ paddingHorizontal: space.lg, gap: space.md }}>
        <Card style={{ gap: 10 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
            <Text variant="heading">{stats.done} of {stats.total} done</Text>
            <Text variant="mono" tone="primary">{Math.round(stats.percent)}%</Text>
          </View>
          <ProgressBar value={stats.percent} tone={stats.percent >= 100 ? "success" : "primary"} />
        </Card>
        <Button label="Add topic" icon="add" onPress={() => setSheet({ open: true, item: null })} />
      </View>

      <ChipRow>
        <Chip label="All" selected={category === "all"} count={data?.length ?? 0} onPress={() => setCategory("all")} />
        {PREP_CATEGORIES.map((c) => (
          <Chip
            key={c}
            label={CATEGORY_LABELS[c]}
            selected={category === c}
            count={(data ?? []).filter((i) => i.category === c).length}
            onPress={() => setCategory(c)}
          />
        ))}
      </ChipRow>

      <View style={{ paddingHorizontal: space.lg, gap: space.sm }}>
        {isPending ? <SkeletonList count={4} /> : null}
        {isError ? <ErrorState error={error} onRetry={() => void refetch()} /> : null}
        {data && !visible.length ? (
          <EmptyState
            icon="book-outline"
            title={category === "all" ? "No topics yet" : "Nothing in this category"}
            description="Add the topics you want to be interview-ready on."
            actionLabel="Add topic"
            onAction={() => setSheet({ open: true, item: null })}
          />
        ) : null}
        {visible.map((item) => (
          <Card key={item.id} onPress={() => setSheet({ open: true, item })}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${item.topic}: ${item.status}. Tap to change status.`}
                hitSlop={10}
                onPress={() => {
                  haptics.light()
                  update.mutate({ id: item.id, patch: { status: NEXT_STATUS[item.status] } })
                }}
              >
                <Icon name={STATUS_ICON[item.status]} size={26} color={item.status === "done" ? "success" : item.status === "doing" ? "warning" : "muted"} />
              </Pressable>
              <View style={{ flex: 1, gap: 6 }}>
                <Text
                  style={{ fontWeight: "600", textDecorationLine: item.status === "done" ? "line-through" : "none" }}
                  tone={item.status === "done" ? "muted" : "default"}
                >
                  {item.topic}
                </Text>
                <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                  <Badge label={CATEGORY_LABELS[item.category]} />
                  <Stars value={item.confidence} onChange={(confidence) => update.mutate({ id: item.id, patch: { confidence } })} />
                </View>
              </View>
            </View>
          </Card>
        ))}
      </View>

      <PrepSheet visible={sheet.open} item={sheet.item} onClose={() => setSheet({ open: false, item: null })} />
    </Screen>
  )
}

import { useRouter } from "expo-router"
import { useCallback, useMemo, useRef, useState } from "react"
import {
  FlatList,
  RefreshControl,
  View,
  useWindowDimensions,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

import { useMoveOpportunity, useOpportunities } from "@/api/opportunities"
import type { Opportunity, Source, Stage } from "@/api/types"
import { STAGES } from "@/api/types"
import { Chip, ChipRow } from "@/components/ui/chip"
import { IconButton } from "@/components/ui/icon-button"
import { OptionSheet } from "@/components/ui/option-sheet"
import { ScreenHeader } from "@/components/ui/screen"
import { SearchBar } from "@/components/ui/search-bar"
import { SkeletonList } from "@/components/ui/skeleton"
import { EmptyState, ErrorState } from "@/components/ui/states"
import { OpportunityCard } from "@/features/pipeline/opportunity-card"
import { PRIORITY_OPTIONS, SOURCE_OPTIONS, STAGE_OPTIONS } from "@/features/pipeline/options"
import { haptics } from "@/lib/haptics"
import { useDebouncedValue } from "@/lib/use-debounced-value"
import { STAGE_LABELS } from "@/lib/format"
import { space } from "@/theme/tokens"
import { useTheme } from "@/theme/theme"

export default function PipelineScreen() {
  const router = useRouter()
  const { colors } = useTheme()
  const { width } = useWindowDimensions()
  const pager = useRef<FlatList<Stage>>(null)

  const [stageIndex, setStageIndex] = useState(1) // start on "applied", where the action is
  const [search, setSearch] = useState("")
  const [priority, setPriority] = useState<number | undefined>()
  const [source, setSource] = useState<Source | undefined>()
  const [pickingSource, setPickingSource] = useState(false)
  const [moving, setMoving] = useState<Opportunity | null>(null)

  const q = useDebouncedValue(search.trim(), 300)
  const { data, isPending, isError, error, refetch, isRefetching } = useOpportunities({
    priority,
    source,
    q: q || undefined,
  })
  const move = useMoveOpportunity()

  const byStage = useMemo(() => {
    const map = new Map<Stage, Opportunity[]>(STAGES.map((s) => [s, []]))
    for (const o of data ?? []) map.get(o.stage)?.push(o)
    return map
  }, [data])

  const goTo = useCallback((index: number) => {
    setStageIndex(index)
    pager.current?.scrollToIndex({ index, animated: true })
  }, [])

  const onSettle = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const index = Math.round(e.nativeEvent.contentOffset.x / width)
    if (index !== stageIndex) {
      haptics.tap()
      setStageIndex(index)
    }
  }

  const open = (id: number) => router.push({ pathname: "/opportunity/[id]", params: { id } })
  const filtered = priority !== undefined || source !== undefined || q !== ""

  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ paddingHorizontal: space.lg, gap: space.md, paddingTop: space.sm }}>
        <ScreenHeader
          title="Pipeline"
          subtitle={data ? `${data.length} opportunit${data.length === 1 ? "y" : "ies"}` : undefined}
          right={
            <IconButton icon="add" label="Add opportunity" filled onPress={() => router.push("/opportunity/form")} />
          }
        />
        <SearchBar value={search} onChangeText={setSearch} placeholder="Search company or role" />
      </View>

      <View style={{ gap: space.sm, marginTop: space.md }}>
        <ChipRow>
          <Chip label="Any priority" selected={priority === undefined} onPress={() => setPriority(undefined)} />
          {PRIORITY_OPTIONS.map((p) => (
            <Chip
              key={p.value}
              label={p.label}
              selected={priority === p.value}
              onPress={() => setPriority(priority === p.value ? undefined : p.value)}
            />
          ))}
          <Chip
            label={source ? `Source: ${SOURCE_OPTIONS.find((s) => s.value === source)?.label}` : "Any source"}
            selected={source !== undefined}
            onPress={() => setPickingSource(true)}
          />
        </ChipRow>
        <ChipRow>
          {STAGES.map((stage, index) => (
            <Chip
              key={stage}
              label={STAGE_LABELS[stage]}
              count={byStage.get(stage)?.length ?? 0}
              selected={index === stageIndex}
              onPress={() => goTo(index)}
            />
          ))}
        </ChipRow>
      </View>

      {isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : (
        <FlatList
          ref={pager}
          data={STAGES as readonly Stage[] as Stage[]}
          keyExtractor={(stage) => stage}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          initialScrollIndex={stageIndex}
          getItemLayout={(_, index) => ({ length: width, offset: width * index, index })}
          onMomentumScrollEnd={onSettle}
          style={{ marginTop: space.md }}
          renderItem={({ item: stage }) => {
            const items = byStage.get(stage) ?? []
            return (
              <View style={{ width }}>
                <FlatList
                  data={items}
                  keyExtractor={(o) => String(o.id)}
                  contentContainerStyle={{
                    padding: space.lg,
                    paddingTop: space.sm,
                    gap: space.md,
                    paddingBottom: 120,
                    flexGrow: 1,
                  }}
                  refreshControl={
                    <RefreshControl
                      refreshing={isRefetching && !isPending}
                      onRefresh={() => void refetch()}
                      tintColor={colors.primary}
                    />
                  }
                  ListEmptyComponent={
                    isPending ? (
                      <SkeletonList count={3} />
                    ) : (
                      <EmptyState
                        icon="albums-outline"
                        title={filtered ? "No matches" : `Nothing in ${STAGE_LABELS[stage]}`}
                        description={
                          filtered
                            ? "Try clearing a filter."
                            : "Move an opportunity here, or add a new one."
                        }
                        actionLabel={filtered ? undefined : "Add opportunity"}
                        onAction={() => router.push("/opportunity/form")}
                      />
                    )
                  }
                  renderItem={({ item }) => (
                    <OpportunityCard
                      opportunity={item}
                      onOpen={() => open(item.id)}
                      onMove={() => setMoving(item)}
                    />
                  )}
                />
              </View>
            )
          }}
        />
      )}

      <OptionSheet
        visible={pickingSource}
        title="Source"
        options={[{ value: "all" as const, label: "Any source" }, ...SOURCE_OPTIONS]}
        value={source ?? "all"}
        onSelect={(value) => setSource(value === "all" ? undefined : value)}
        onClose={() => setPickingSource(false)}
      />
      <OptionSheet
        visible={moving !== null}
        title={moving ? `Move ${moving.company} to…` : "Move to…"}
        options={STAGE_OPTIONS}
        value={moving?.stage}
        onSelect={(stage) => {
          if (moving && stage !== moving.stage) {
            haptics.success()
            move.mutate({ id: moving.id, stage })
          }
        }}
        onClose={() => setMoving(null)}
      />
    </SafeAreaView>
  )
}

import { BookOpenCheck, Pencil, Plus, StickyNote, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { useDeletePrepItem, usePrepItems, useUpdatePrepItem } from "@/api/prep-items"
import {
  PREP_CATEGORIES,
  PREP_STATUSES,
  type PrepCategory,
  type PrepItem,
  type PrepStatus,
} from "@/api/types"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PageHeader } from "@/components/common/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { CATEGORY_LABELS } from "@/features/prep/categories"
import { ConfidenceRating } from "@/features/prep/confidence-rating"
import { PrepItemDialog } from "@/features/prep/prep-item-dialog"
import { titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"

const ALL = "all"

interface Stats {
  total: number
  done: number
  percent: number
  avgConfidence: number | null
}

function statsOf(items: PrepItem[]): Stats {
  const done = items.filter((i) => i.status === "done").length
  const total = items.length
  return {
    total,
    done,
    percent: total === 0 ? 0 : Math.round((done / total) * 100),
    avgConfidence: total === 0 ? null : items.reduce((sum, i) => sum + i.confidence, 0) / total,
  }
}

function PrepRow({
  item,
  onEdit,
  onDelete,
}: {
  item: PrepItem
  onEdit: (item: PrepItem) => void
  onDelete: (item: PrepItem) => void
}) {
  const update = useUpdatePrepItem()
  const done = item.status === "done"

  const changeStatus = (value: string) => {
    const status = PREP_STATUSES.find((s) => s === value)
    if (status) update.mutate({ id: item.id, patch: { status } })
  }

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300">
      <Checkbox
        className="size-5 sm:size-4 [@media(pointer:coarse)]:size-6"
        checked={done}
        aria-label={`Mark "${item.topic}" ${done ? "not done" : "done"}`}
        onCheckedChange={(checked) =>
          update.mutate({ id: item.id, patch: { status: checked === true ? "done" : "todo" } })
        }
      />
      <div className="min-w-0 flex-1 basis-56">
        <p className={cn("font-medium", done && "text-muted-foreground line-through")}>
          {item.topic}
        </p>
        {item.notes ? (
          <p className="mt-0.5 flex items-start gap-1 text-sm text-muted-foreground">
            <StickyNote className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span className="line-clamp-2">{item.notes}</span>
          </p>
        ) : null}
      </div>
      <Select value={item.status} onValueChange={changeStatus}>
        <SelectTrigger size="sm" className="w-28" aria-label={`Status for ${item.topic}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {PREP_STATUSES.map((s) => (
            <SelectItem key={s} value={s}>
              {titleCase(s)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <ConfidenceRating
        label={item.topic}
        value={item.confidence}
        onChange={(confidence) => update.mutate({ id: item.id, patch: { confidence } })}
      />
      <div className="flex">
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Edit ${item.topic}`}
          onClick={() => onEdit(item)}
        >
          <Pencil />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Delete ${item.topic}`}
          onClick={() => onDelete(item)}
        >
          <Trash2 />
        </Button>
      </div>
    </li>
  )
}

function CategoryCard({
  category,
  items,
  onEdit,
  onDelete,
}: {
  category: PrepCategory
  items: PrepItem[]
  onEdit: (item: PrepItem) => void
  onDelete: (item: PrepItem) => void
}) {
  const stats = statsOf(items)
  return (
    <Card>
      <CardHeader>
        <CardTitle>{CATEGORY_LABELS[category]}</CardTitle>
        <CardDescription className="font-mono">
          {stats.done}/{stats.total} done
          {stats.avgConfidence !== null
            ? ` · avg confidence ${stats.avgConfidence.toFixed(1)}/5`
            : ""}
        </CardDescription>
        <Progress
          value={stats.percent}
          aria-label={`${CATEGORY_LABELS[category]} progress`}
          className="mt-2"
        />
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {items.map((item) => (
            <PrepRow key={item.id} item={item} onEdit={onEdit} onDelete={onDelete} />
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

export function PrepPage() {
  const { data, isPending, isError, error, refetch } = usePrepItems()
  const remove = useDeletePrepItem()
  const [filter, setFilter] = useState<string>(ALL)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<PrepItem | null>(null)
  const [deleting, setDeleting] = useState<PrepItem | null>(null)

  const grouped = useMemo(() => {
    const map = new Map<PrepCategory, PrepItem[]>(PREP_CATEGORIES.map((c) => [c, []]))
    for (const item of data ?? []) map.get(item.category)?.push(item)
    return map
  }, [data])

  const overall = statsOf(data ?? [])
  const visible = PREP_CATEGORIES.filter(
    (c) => (filter === ALL || filter === c) && (grouped.get(c)?.length ?? 0) > 0,
  )
  const defaultCategory: PrepCategory = PREP_CATEGORIES.find((c) => c === filter) ?? "python"

  const openAdd = () => {
    setEditing(null)
    setDialogOpen(true)
  }
  const openEdit = (item: PrepItem) => {
    setEditing(item)
    setDialogOpen(true)
  }

  const statusCounts: Record<PrepStatus, number> = { todo: 0, doing: 0, done: 0 }
  for (const item of data ?? []) statusCounts[item.status] += 1

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Prep"
        description="Topics to be ready for, with how confident you feel about each."
        actions={
          <Button onClick={openAdd}>
            <Plus />
            Add topic
          </Button>
        }
      />

      {isPending ? (
        <div className="space-y-6" aria-busy="true" aria-label="Loading prep topics">
          <Skeleton className="h-28" />
          <Skeleton className="h-64" />
        </div>
      ) : null}
      {isError ? <ErrorState message={error.message} onRetry={() => void refetch()} /> : null}

      {data && data.length === 0 ? (
        <EmptyState
          icon={BookOpenCheck}
          title="No prep topics yet"
          description="List the topics you want to revise, such as async Python, indexes or system design, and rate your confidence as you go."
          action={<Button onClick={openAdd}>Add your first topic</Button>}
        />
      ) : null}

      {data && data.length > 0 ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Overall progress</CardTitle>
              <CardDescription className="font-mono">
                {overall.done}/{overall.total} done · {statusCounts.doing} in progress ·{" "}
                {statusCounts.todo} to do
                {overall.avgConfidence !== null
                  ? ` · avg confidence ${overall.avgConfidence.toFixed(1)}/5`
                  : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-row items-center gap-4">
              <div className="flex-1">
                <Progress value={overall.percent} aria-label="Overall prep progress" />
              </div>
              <span className="w-12 text-right font-mono text-sm">{overall.percent}%</span>
            </CardContent>
          </Card>

          <Tabs value={filter} onValueChange={setFilter}>
            <TabsList className="h-auto w-full justify-start overflow-x-auto sm:w-fit">
              <TabsTrigger value={ALL} className="flex-none">
                All
              </TabsTrigger>
              {PREP_CATEGORIES.map((c) => (
                <TabsTrigger key={c} value={c} className="flex-none">
                  {CATEGORY_LABELS[c]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {visible.length === 0 ? (
            <EmptyState
              icon={BookOpenCheck}
              title="Nothing in this category"
              description="Add a topic to start tracking it."
              action={<Button onClick={openAdd}>Add topic</Button>}
            />
          ) : (
            visible.map((category) => (
              <CategoryCard
                key={category}
                category={category}
                items={grouped.get(category) ?? []}
                onEdit={openEdit}
                onDelete={setDeleting}
              />
            ))
          )}
        </div>
      ) : null}

      <PrepItemDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        item={editing}
        defaultCategory={defaultCategory}
      />

      <Dialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this topic?</DialogTitle>
            <DialogDescription>
              &ldquo;{deleting?.topic}&rdquo; and its notes will be removed. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleting(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => {
                if (!deleting) return
                remove.mutate(deleting.id, {
                  onSuccess: () => {
                    toast.success("Topic deleted")
                    setDeleting(null)
                  },
                  onError: (e) => toast.error("Could not delete", { description: e.message }),
                })
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

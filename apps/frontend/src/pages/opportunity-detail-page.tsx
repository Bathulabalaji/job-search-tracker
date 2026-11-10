import { ArrowLeft, MessageSquarePlus, Pencil, Trash2, TriangleAlert } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"

import { ApiError } from "@/api/client"
import { useDeleteOpportunity, useMoveOpportunity, useOpportunity } from "@/api/opportunities"
import { STAGES, type Opportunity, type Stage } from "@/api/types"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PriorityBadge } from "@/components/common/priority-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToday } from "@/api/dashboard"
import { ContactsCard, DetailsCard, FollowupsCard } from "@/features/detail/side-cards"
import { Timeline } from "@/features/detail/timeline"
import { EditOpportunityDialog } from "@/features/opportunities/edit-opportunity-dialog"
import { useQuickActions } from "@/features/quick-actions/quick-actions-context"
import { STAGE_LABELS } from "@/lib/format"

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading opportunity">
      <Skeleton className="h-16 w-1/2" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-96 lg:col-span-2" />
        <Skeleton className="h-96" />
      </div>
    </div>
  )
}

function DeleteDialog({
  opportunity,
  open,
  onOpenChange,
}: {
  opportunity: Opportunity
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const remove = useDeleteOpportunity()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete {opportunity.company}?</DialogTitle>
          <DialogDescription>
            This also deletes its interactions and follow-ups. Contacts are kept but unlinked. This
            cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(opportunity.id, {
                onSuccess: () => {
                  toast.success(`Deleted ${opportunity.company}`)
                  void navigate("/pipeline")
                },
                onError: (error) => toast.error("Could not delete", { description: error.message }),
              })
            }
          >
            {remove.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Detail({ opportunity }: { opportunity: Opportunity }) {
  const move = useMoveOpportunity()
  const { openLogInteraction } = useQuickActions()
  const today = useToday()
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const changeStage = (stage: Stage) => {
    if (stage !== opportunity.stage) move.mutate({ id: opportunity.id, stage })
  }
  const onStageSelect = (value: string) => {
    const stage = STAGES.find((s) => s === value)
    if (stage) changeStage(stage)
  }
  // "Overdue" is judged against the server's idea of today, so wait for it.
  const todayIso = today.data?.today

  return (
    <div className="mx-auto max-w-6xl">
      <Link
        to="/pipeline"
        className="mb-3 inline-flex min-h-8 items-center gap-1 rounded-sm pr-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden />
        Pipeline
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">{opportunity.company}</h1>
          <p className="text-muted-foreground">{opportunity.role}</p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Select value={opportunity.stage} onValueChange={onStageSelect}>
              <SelectTrigger className="w-full min-w-0 sm:w-52" aria-label="Stage">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STAGES.map((stage) => (
                  <SelectItem key={stage} value={stage}>
                    {STAGE_LABELS[stage]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <PriorityBadge priority={opportunity.priority} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => openLogInteraction(opportunity.id)}>
            <MessageSquarePlus />
            Log interaction
          </Button>
          <Button variant="outline" onClick={() => setEditing(true)}>
            <Pencil />
            Edit
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Delete opportunity"
            onClick={() => setDeleting(true)}
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      {opportunity.ghosted_suggestion ? (
        <div
          role="status"
          className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm"
        >
          <TriangleAlert className="size-4 text-amber-700 dark:text-amber-300" aria-hidden />
          <span className="flex-1">
            No contact for <span className="font-mono">{opportunity.days_since_contact}</span> days.
            This one may have ghosted you.
          </span>
          <Button size="sm" variant="outline" onClick={() => changeStage("ghosted")}>
            Mark as ghosted
          </Button>
        </div>
      ) : null}

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-3">
        <Card className="min-w-0 lg:col-span-2">
          <CardContent>
            <Tabs defaultValue="timeline">
              <TabsList>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
                <TabsTrigger value="jd">Job description</TabsTrigger>
              </TabsList>
              <TabsContent value="timeline" className="pt-6">
                <Timeline
                  opportunityId={opportunity.id}
                  onLog={() => openLogInteraction(opportunity.id)}
                />
              </TabsContent>
              <TabsContent value="jd" className="pt-6">
                {opportunity.jd_text ? (
                  <div className="max-w-none whitespace-pre-wrap text-sm leading-relaxed">
                    {opportunity.jd_text}
                  </div>
                ) : (
                  <EmptyState
                    icon={Pencil}
                    title="No job description saved"
                    description="Paste the JD so you can revisit it before interviews."
                    action={<Button onClick={() => setEditing(true)}>Add job description</Button>}
                  />
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <div className="min-w-0 space-y-6">
          <DetailsCard opportunity={opportunity} />
          <FollowupsCard opportunity={opportunity} today={todayIso} />
          <ContactsCard opportunity={opportunity} />
        </div>
      </div>

      <EditOpportunityDialog opportunity={opportunity} open={editing} onOpenChange={setEditing} />
      <DeleteDialog opportunity={opportunity} open={deleting} onOpenChange={setDeleting} />
    </div>
  )
}

export function OpportunityDetailPage() {
  const params = useParams()
  const id = Number(params["id"])
  const validId = Number.isInteger(id) && id > 0
  const query = useOpportunity(id, validId)

  if (
    !validId ||
    (query.isError && query.error instanceof ApiError && query.error.status === 404)
  ) {
    return (
      <EmptyState
        icon={TriangleAlert}
        title="Opportunity not found"
        description="It may have been deleted."
        action={
          <Button asChild>
            <Link to="/pipeline">Back to pipeline</Link>
          </Button>
        }
      />
    )
  }
  if (query.isPending) return <DetailSkeleton />
  if (query.isError)
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
  return <Detail opportunity={query.data} />
}

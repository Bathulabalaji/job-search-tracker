import { Loader2, RefreshCw, SlidersHorizontal, Target, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { ApiError } from "@/api/client"
import {
  useDismissRecommendation,
  useRecommendations,
  useRefreshRecommendations,
  useSearchProfile,
} from "@/api/matching"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { PageHeader } from "@/components/common/page-header"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { JobCard } from "@/features/assistant/job-cards"
import { SearchProfileDialog } from "@/features/matching/search-profile-dialog"

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Try again."
}

export function RecommendationsPage() {
  const feed = useRecommendations()
  const profile = useSearchProfile()
  const refresh = useRefreshRecommendations()
  const dismiss = useDismissRecommendation()
  const [editing, setEditing] = useState(false)
  const items = feed.data ?? []

  const onRefresh = () =>
    refresh.mutate(undefined, {
      onSuccess: (result) => {
        const first = result.notices[0]?.message
        if (result.added > 0)
          toast.success(`${result.added} new job${result.added === 1 ? "" : "s"}`)
        else toast.info(first ?? "Nothing new that matches your resumes yet.")
      },
      onError: (error) => toast.error(message(error)),
    })

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Jobs for you"
        description="Fresh postings ranked by how closely they match your uploaded resumes."
        actions={
          <>
            <Button variant="outline" onClick={() => setEditing(true)} disabled={!profile.data}>
              <SlidersHorizontal /> Search profile
            </Button>
            <Button onClick={onRefresh} disabled={refresh.isPending}>
              {refresh.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Find new
              jobs
            </Button>
          </>
        }
      />

      {feed.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : feed.isError ? (
        <ErrorState message={message(feed.error)} onRetry={() => void feed.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Target}
          title="No recommendations yet"
          description="Upload a resume PDF, then choose Find new jobs. Each search uses a little of the daily search allowance, so it is limited to a couple of times a day."
        />
      ) : (
        <ul className="grid gap-2" aria-label="Recommended jobs">
          {items.map((rec) => (
            <JobCard
              key={rec.id}
              job={rec.job}
              note={
                <>
                  {Math.round(rec.vector_score * 100)}% similar
                  {rec.best_resume_label ? ` · best resume: ${rec.best_resume_label}` : ""}
                </>
              }
              extraActions={
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Dismiss ${rec.job.title}`}
                  onClick={() => dismiss.mutate(rec.id)}
                >
                  <X /> Dismiss
                </Button>
              }
            />
          ))}
        </ul>
      )}

      {profile.data ? (
        <SearchProfileDialog open={editing} onOpenChange={setEditing} profile={profile.data} />
      ) : null}
    </div>
  )
}

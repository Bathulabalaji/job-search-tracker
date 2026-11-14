import { FileSearch, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { ApiError } from "@/api/client"
import { useChatConfig } from "@/api/chat"
import { useStoredMatch, useRunMatch } from "@/api/matching"
import { useUpdateOpportunity } from "@/api/opportunities"
import type { Opportunity } from "@/api/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { MatchBreakdown } from "@/features/matching/match-breakdown"

function describe(error: unknown): string {
  return error instanceof ApiError ? error.message : "Couldn't compare your resumes right now."
}

/** "Which resume fits?": compares the user's uploaded resumes with this JD. */
export function ResumeFitCard({ opportunity }: { opportunity: Opportunity }) {
  const config = useChatConfig()
  const enabled = config.data?.matching === true
  const stored = useStoredMatch(opportunity.id, enabled)
  const run = useRunMatch(opportunity.id)
  const update = useUpdateOpportunity(opportunity.id)
  if (!enabled) return null

  const result = run.data ?? stored.data ?? null
  const best = result?.per_resume.find((m) => m.resume_id === result.best_resume_id)

  const compare = (force: boolean) =>
    run.mutate(force, { onError: (e) => toast.error(describe(e)) })
  const useScore = () => {
    if (best?.score == null) return
    update.mutate(
      { fit_score: best.score },
      { onSuccess: () => toast.success(`Fit score set to ${best.score}`) },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Which resume fits?</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {stored.isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : result ? (
          <>
            <MatchBreakdown result={result} />
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => compare(true)}
                disabled={run.isPending}
              >
                {run.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Re-check
              </Button>
              {best?.score != null && best.score !== opportunity.fit_score ? (
                <Button size="sm" onClick={useScore} disabled={update.isPending}>
                  Use {best.score} as fit score
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Compare your uploaded resumes with this job description to see which one fits best,
              what it covers and what is missing.
            </p>
            <Button className="w-full" onClick={() => compare(false)} disabled={run.isPending}>
              {run.isPending ? <Loader2 className="animate-spin" /> : <FileSearch />} Compare my
              resumes
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}

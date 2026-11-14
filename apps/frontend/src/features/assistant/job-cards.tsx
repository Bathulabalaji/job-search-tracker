import {
  BadgeCheck,
  Briefcase,
  CircleHelp,
  ExternalLink,
  Loader2,
  Plus,
  XCircle,
} from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import type { ChatAttachment, JobCardData, MatchCardData } from "@/api/chat"
import { ApiError } from "@/api/client"
import { useTrackJob } from "@/api/jobs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MatchBreakdown } from "@/features/matching/match-breakdown"
import { cn } from "@/lib/utils"

const SITE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  naukri: "Naukri",
  indeed: "Indeed",
  company: "Company site",
  other: "Job board",
}

function postedLabel(postedAt: string | null, now: Date = new Date()): string | null {
  if (!postedAt) return null
  const days = Math.floor((now.getTime() - new Date(postedAt).getTime()) / 86_400_000)
  if (days <= 0) return "Posted today"
  if (days === 1) return "Posted yesterday"
  return `Posted ${days} days ago`
}

/** Only http(s) links from the server's structured result are ever rendered. */
function safeHref(url: string): string | undefined {
  try {
    const parsed = new URL(url)
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : undefined
  } catch {
    return undefined
  }
}

function ActiveBadge({ status }: { status: string }) {
  if (status === "active")
    return (
      <Badge variant="secondary" className="gap-1">
        <BadgeCheck aria-hidden /> Verified open
      </Badge>
    )
  if (status === "inactive")
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle aria-hidden /> Looks closed
      </Badge>
    )
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <CircleHelp aria-hidden /> Not verified
    </Badge>
  )
}

export function JobCard({
  job,
  note,
  extraActions,
}: {
  job: JobCardData
  /** A line under the badges, e.g. why this job was recommended. */
  note?: React.ReactNode
  /** Buttons shown before Open and Track, e.g. Dismiss. */
  extraActions?: React.ReactNode
}) {
  const track = useTrackJob()
  const [trackedId, setTrackedId] = useState<number | null>(job.tracked_opportunity_id)
  const href = safeHref(job.apply_url)
  const meta = [job.location, job.work_mode, job.salary_text].filter(Boolean).join(" · ")
  const posted = postedLabel(job.posted_at)

  const onTrack = () => {
    track.mutate(
      { id: job.id },
      {
        onSuccess: (opportunity) => {
          setTrackedId(opportunity.id)
          toast.success(`Added ${opportunity.company} to your pipeline`)
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "already_tracked") {
            toast.info("This job is already in your pipeline.")
          } else {
            toast.error(error instanceof Error ? error.message : "Couldn't add the job.")
          }
        },
      },
    )
  }

  return (
    <li className="rounded-lg border bg-card p-3 text-card-foreground">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Briefcase className="size-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-medium leading-snug">{job.title}</p>
          <p className="text-sm text-muted-foreground">
            {job.company}
            {meta ? <span> · {meta}</span> : null}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <Badge variant="outline">{SITE_LABELS[job.source_site] ?? "Job board"}</Badge>
            <ActiveBadge status={job.active_status} />
            {posted ? <span className="text-xs text-muted-foreground">{posted}</span> : null}
          </div>
          {note ? <p className="pt-0.5 text-xs text-muted-foreground">{note}</p> : null}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        {extraActions}
        {href ? (
          <Button asChild size="sm" variant="outline">
            <a href={href} target="_blank" rel="noopener noreferrer nofollow">
              <ExternalLink /> Open
            </a>
          </Button>
        ) : null}
        {trackedId !== null ? (
          <Button asChild size="sm" variant="secondary">
            <Link to={`/opportunities/${trackedId}`}>In pipeline</Link>
          </Button>
        ) : (
          <Button size="sm" onClick={onTrack} disabled={track.isPending}>
            {track.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Track
          </Button>
        )}
      </div>
    </li>
  )
}

function MatchCard({ match }: { match: MatchCardData }) {
  return (
    <li className="space-y-2 rounded-lg border bg-muted/30 p-3">
      <p className="text-sm font-medium">Resume fit · {match.target_label}</p>
      <MatchBreakdown result={match} />
      {match.target === "opportunity" ? (
        <div className="flex justify-end">
          <Button asChild size="sm" variant="outline">
            <Link to={`/opportunities/${match.target_id}`}>Open opportunity</Link>
          </Button>
        </div>
      ) : null}
    </li>
  )
}

export function AttachmentList({
  items,
  className,
}: {
  items: ChatAttachment[]
  className?: string
}) {
  const jobs = items.filter((a): a is JobCardData => a.type === "job")
  const matches = items.filter((a): a is MatchCardData => a.type === "match")
  if (!jobs.length && !matches.length) return null
  return (
    <ul className={cn("mt-3 grid gap-2", className)} aria-label="Results">
      {matches.map((match) => (
        <MatchCard key={`${match.target}-${match.target_id}`} match={match} />
      ))}
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </ul>
  )
}

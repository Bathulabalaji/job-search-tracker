import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import type { MatchResult, ResumeMatch } from "@/api/matching"

/** One resume's score, the skills it covers and lacks, and what to change. */
function ResumeRow({ match, best }: { match: ResumeMatch; best: boolean }) {
  return (
    <li className="space-y-2 rounded-lg border bg-card p-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 truncate font-medium">
          {match.label}
          {best ? (
            <Badge variant="secondary" className="ml-2 align-middle">
              Best fit
            </Badge>
          ) : null}
        </p>
        <span className="shrink-0 font-mono text-sm">
          {match.score === null ? "—" : `${match.score}/100`}
        </span>
      </div>
      <Progress value={match.score ?? 0} aria-label={`${match.label} fit`} />
      {match.vector_score !== null ? (
        <p className="text-xs text-muted-foreground">
          Text similarity {Math.round(match.vector_score * 100)}%
        </p>
      ) : null}
      {match.matched_skills.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Covers</span>
          {match.matched_skills.map((skill) => (
            <Badge key={skill} variant="secondary" className="font-normal">
              {skill}
            </Badge>
          ))}
        </div>
      ) : null}
      {match.missing_skills.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">Missing</span>
          {match.missing_skills.map((skill) => (
            <Badge key={skill} variant="outline" className="font-normal">
              {skill}
            </Badge>
          ))}
        </div>
      ) : null}
      {match.suggestions.length > 0 ? (
        <ul className="list-disc space-y-0.5 pl-4 text-sm text-muted-foreground">
          {match.suggestions.map((suggestion) => (
            <li key={suggestion}>{suggestion}</li>
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export function MatchBreakdown({ result }: { result: MatchResult }) {
  return (
    <ul className="space-y-2" aria-label="Resume fit">
      {result.per_resume.map((match) => (
        <ResumeRow
          key={match.resume_id}
          match={match}
          best={result.per_resume.length > 1 && match.resume_id === result.best_resume_id}
        />
      ))}
    </ul>
  )
}

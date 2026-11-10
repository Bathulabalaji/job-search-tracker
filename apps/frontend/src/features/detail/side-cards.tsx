import { Check, ExternalLink, Mail, Phone, Plus, UserRound, Users } from "lucide-react"
import { useState } from "react"

import { useContacts } from "@/api/contacts"
import { useFollowups, useUpdateFollowup } from "@/api/followups"
import type { Followup, Opportunity } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate, titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"
import { AddContactDialog } from "./add-contact-dialog"
import { AddFollowupDialog } from "./add-followup-dialog"

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  )
}

export function DetailsCard({ opportunity: o }: { opportunity: Opportunity }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Fit &amp; details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-baseline justify-between text-sm">
            <span className="text-muted-foreground">Fit score</span>
            <span className="font-mono">{o.fit_score === null ? "Not rated" : `${o.fit_score}/100`}</span>
          </div>
          <Progress value={o.fit_score ?? 0} aria-label="Fit score" />
        </div>

        <dl className="divide-y">
          <Row label="Source">{titleCase(o.source)}</Row>
          <Row label="Location">
            {o.location ?? "—"}
            {o.work_mode ? <span className="text-muted-foreground"> · {titleCase(o.work_mode)}</span> : null}
          </Row>
          <Row label="Expected CTC">{o.expected_ctc_note ?? "—"}</Row>
          <Row label="Next action">
            {o.next_action ? (
              <span>
                {o.next_action}
                {o.next_action_due ? (
                  <span className="block font-mono text-xs text-muted-foreground">
                    {formatDate(o.next_action_due)}
                  </span>
                ) : null}
              </span>
            ) : (
              "—"
            )}
          </Row>
          <Row label="Last contact">
            <span className="font-mono">
              {o.last_contact_at ? `${o.days_since_contact}d ago` : "Never"}
            </span>
          </Row>
        </dl>

        {o.stack_tags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {o.stack_tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="font-normal">
                {tag}
              </Badge>
            ))}
          </div>
        ) : null}

        {o.jd_url ? (
          <Button variant="outline" size="sm" asChild className="w-full">
            <a href={o.jd_url} target="_blank" rel="noreferrer noopener">
              <ExternalLink />
              Open job posting
            </a>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function ContactsCard({ opportunity }: { opportunity: Opportunity }) {
  const contacts = useContacts(opportunity.id)
  const [adding, setAdding] = useState(false)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="size-4 text-primary" aria-hidden />
          Contacts
        </CardTitle>
        <CardAction>
          <Button variant="ghost" size="icon" aria-label="Add contact" onClick={() => setAdding(true)}>
            <Plus />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {contacts.isPending ? <Skeleton className="h-16" /> : null}
        {contacts.isError ? (
          <p className="text-sm text-destructive">{contacts.error.message}</p>
        ) : null}
        {contacts.data?.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No contacts yet. Add the recruiter or referrer for this role.
          </p>
        ) : null}
        <ul className="divide-y">
          {contacts.data?.map((c) => (
            <li key={c.id} className="space-y-1 py-3 first:pt-0 last:pb-0">
              <div className="flex items-center gap-2">
                <UserRound className="size-4 text-muted-foreground" aria-hidden />
                <span className="font-medium">{c.name}</span>
                <Badge variant="outline" className="font-normal">
                  {titleCase(c.role)}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 pl-6 text-sm text-muted-foreground">
                {c.email ? (
                  <a className="inline-flex items-center gap-1 hover:underline" href={`mailto:${c.email}`}>
                    <Mail className="size-3" aria-hidden />
                    {c.email}
                  </a>
                ) : null}
                {c.phone ? (
                  <span className="inline-flex items-center gap-1 font-mono">
                    <Phone className="size-3" aria-hidden />
                    {c.phone}
                  </span>
                ) : null}
              </div>
              {c.notes ? <p className="pl-6 text-sm">{c.notes}</p> : null}
            </li>
          ))}
        </ul>
      </CardContent>
      <AddContactDialog
        opportunityId={opportunity.id}
        defaultCompany={opportunity.company}
        open={adding}
        onOpenChange={setAdding}
      />
    </Card>
  )
}

function FollowupItem({ followup, today }: { followup: Followup; today: string | undefined }) {
  const update = useUpdateFollowup()
  const pending = followup.status === "pending"
  const overdue = pending && today !== undefined && followup.due_date < today

  return (
    <li className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm">{formatDate(followup.due_date)}</span>
          <Badge
            variant="outline"
            className={cn(
              "border-transparent font-normal",
              pending
                ? overdue
                  ? "bg-red-500/15 text-red-800 dark:text-red-300"
                  : "bg-indigo-500/15 text-indigo-800 dark:text-indigo-300"
                : "bg-muted text-muted-foreground",
            )}
          >
            {pending ? (overdue ? "Overdue" : "Pending") : titleCase(followup.status)}
          </Badge>
          <span className="text-xs text-muted-foreground">{titleCase(followup.channel)}</span>
        </div>
        {followup.message_draft ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{followup.message_draft}</p>
        ) : null}
      </div>
      {pending ? (
        <Button
          size="sm"
          variant="outline"
          disabled={update.isPending}
          onClick={() =>
            update.mutate({
              id: followup.id,
              opportunityId: followup.opportunity_id,
              patch: { status: "done" },
              message: "Follow-up marked done",
            })
          }
        >
          <Check />
          Done
        </Button>
      ) : null}
    </li>
  )
}

export function FollowupsCard({
  opportunity,
  today,
}: {
  opportunity: Opportunity
  today: string | undefined
}) {
  const followups = useFollowups(opportunity.id)
  const [adding, setAdding] = useState(false)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Follow-ups</CardTitle>
        <CardAction>
          <Button variant="ghost" size="icon" aria-label="Add follow-up" onClick={() => setAdding(true)}>
            <Plus />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {followups.isPending ? <Skeleton className="h-16" /> : null}
        {followups.isError ? (
          <p className="text-sm text-destructive">{followups.error.message}</p>
        ) : null}
        {followups.data?.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None scheduled. Moving to Applied or Screening adds one automatically.
          </p>
        ) : null}
        <ul className="divide-y">
          {followups.data?.map((f) => <FollowupItem key={f.id} followup={f} today={today} />)}
        </ul>
      </CardContent>
      <AddFollowupDialog opportunityId={opportunity.id} open={adding} onOpenChange={setAdding} />
    </Card>
  )
}

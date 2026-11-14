import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  Users,
  Loader2,
  Mail,
  Paperclip,
  Sparkles,
  Undo2,
} from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import {
  useMarkSent,
  usePolish,
  usePreview,
  useSuggestions,
  useTemplates,
  type MessageTemplate,
  type OutreachChannel,
  type PolishInstruction,
} from "@/api/messaging"
import { ApiError } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  fillGap,
  gapsIn,
  gmailLink,
  launch,
  linkedinTarget,
  mailtoLink,
  tooLongForMailto,
} from "./outreach-links"

const CHANNEL_LABELS: Record<OutreachChannel, string> = {
  email: "Email",
  linkedin: "LinkedIn message",
  linkedin_note: "Connection note",
}

const POLISH: { value: PolishInstruction; label: string }[] = [
  { value: "shorter", label: "Make it shorter" },
  { value: "warmer", label: "Warmer tone" },
  { value: "more_formal", label: "More formal" },
  { value: "more_direct", label: "More direct" },
  { value: "fix_grammar", label: "Fix grammar only" },
]

/** The few fields the dialog needs, so a reminder or chat card can open it without a full record. */
export type OpportunityRef = { id: number; company: string; role: string }

export interface MessageDialogProps {
  opportunity: OpportunityRef
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Start on a specific template, e.g. from a follow-up reminder. */
  initial?: { templateKey?: string; channel?: OutreachChannel; contactId?: number | null }
}

export function MessageDialog({ opportunity, open, onOpenChange, initial }: MessageDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>
            Message for {opportunity.company}: {opportunity.role}
          </DialogTitle>
          <DialogDescription>
            Pick a message, check the details, then open it in your own mail app or LinkedIn. You
            send it yourself; nothing is sent from here.
          </DialogDescription>
        </DialogHeader>
        {/* Mounted only while open, so every opening starts fresh. */}
        <Composer opportunity={opportunity} initial={initial} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  )
}

interface Draft {
  key: string
  subject: string | null
  body: string
}

function Composer({
  opportunity,
  initial,
  onDone,
}: {
  opportunity: OpportunityRef
  initial: MessageDialogProps["initial"]
  onDone: () => void
}) {
  const suggestions = useSuggestions(opportunity.id)
  const templates = useTemplates()
  const [templateState, setTemplate] = useState<string | null>(initial?.templateKey ?? null)
  const [channelState, setChannel] = useState<OutreachChannel | null>(initial?.channel ?? null)
  const [contactState, setContact] = useState<number | null | undefined>(
    initial?.contactId === undefined ? undefined : initial.contactId,
  )
  const [draft, setDraft] = useState<Draft | null>(null)
  const [undo, setUndo] = useState<{ subject: string | null; body: string } | null>(null)
  const [needsConfirm, setNeedsConfirm] = useState(false)
  const [requestId] = useState(() => crypto.randomUUID())

  const advice = suggestions.data
  const all = templates.data ?? []
  const firstDue = advice?.suggestions.find((s) => s.kind === "send" && s.due)
  const firstAny = advice?.suggestions.find((s) => s.kind === "send" || s.kind === "wait")
  const fallback = firstDue ?? firstAny ?? null
  const templateKey = templateState ?? fallback?.template_key ?? all[0]?.key ?? null
  const template = all.find((t) => t.key === templateKey) ?? null
  const channels = template?.variants.map((v) => v.channel) ?? []
  const channel: OutreachChannel =
    channelState && channels.includes(channelState)
      ? channelState
      : fallback?.template_key === templateKey &&
          fallback.channel &&
          channels.includes(fallback.channel)
        ? fallback.channel
        : (channels[0] ?? "email")
  const suggestedContact =
    fallback?.template_key === templateKey ? (fallback.contact_id ?? null) : null
  const contactId =
    contactState === undefined
      ? (suggestedContact ?? advice?.contacts[0]?.id ?? null)
      : contactState
  const contact = advice?.contacts.find((c) => c.id === contactId) ?? null

  const preview = usePreview(opportunity.id, templateKey, channel, contactId)
  const key = `${templateKey}|${channel}|${contactId}`
  const live = preview.data && !preview.isPlaceholderData ? preview.data : null
  const text: Draft | null =
    draft?.key === key ? draft : live ? { key, subject: live.subject, body: live.body } : null
  const gaps = text ? gapsIn(`${text.subject ?? ""}\n${text.body}`) : []
  const uniqueGaps = [...new Set(gaps)]

  const polish = usePolish(opportunity.id)
  const markSent = useMarkSent(opportunity.id)

  const edit = (next: { subject?: string | null; body?: string }) => {
    if (!text) return
    setDraft({
      key,
      subject: next.subject !== undefined ? next.subject : text.subject,
      body: next.body ?? text.body,
    })
    setNeedsConfirm(false)
  }

  const pick = (nextKey: string) => {
    setTemplate(nextKey)
    setChannel(null)
    setContact(undefined)
    setDraft(null)
    setUndo(null)
    setNeedsConfirm(false)
  }

  const fill = (label: string, value: string) =>
    edit({
      subject: text?.subject ? fillGap(text.subject, label, value) : text?.subject,
      body: fillGap(text?.body ?? "", label, value),
    })

  const copyText = async (): Promise<boolean> => {
    if (!text) return false
    try {
      await navigator.clipboard.writeText(
        text.subject ? `Subject: ${text.subject}\n\n${text.body}` : text.body,
      )
      return true
    } catch {
      toast.error("Couldn't copy. Select the text and copy it yourself.")
      return false
    }
  }

  const asDraft = () => ({
    to: live?.to ?? null,
    subject: text?.subject ?? null,
    body: text?.body ?? "",
    from: live?.from_email ?? null,
  })

  const openEmail = async () => {
    if (!text) return
    if (tooLongForMailto(asDraft())) {
      if (await copyText())
        toast.info("Too long for a mail link, so it was copied. Paste it into the email.")
      launch(mailtoLink({ ...asDraft(), body: "" }))
      return
    }
    launch(mailtoLink(asDraft()))
  }

  const openGmail = () => window.open(gmailLink(asDraft()), "_blank", "noopener,noreferrer")

  const openLinkedIn = async () => {
    const target = linkedinTarget(contact, opportunity.company)
    if (await copyText()) {
      toast.success(
        target.isSearch
          ? "Copied. Opening a LinkedIn search for them: paste the message once you're in their profile."
          : "Message copied. Open their message box and paste it.",
      )
    }
    window.open(target.url, "_blank", "noopener,noreferrer")
  }

  const runPolish = (instruction: PolishInstruction) => {
    if (!text) return
    polish.mutate(
      { subject: text.subject, body: text.body, instruction },
      {
        onSuccess: (result) => {
          if (!result.changed) {
            toast.info(result.notice ?? "Nothing to change.")
            return
          }
          setUndo({ subject: text.subject, body: text.body })
          setDraft({ key, subject: result.subject, body: result.body })
        },
        onError: (error) =>
          toast.error(
            error instanceof ApiError ? error.message : "Couldn't rewrite that right now.",
          ),
      },
    )
  }

  const sent = () => {
    if (!text || !live) return
    if (uniqueGaps.length > 0 && !needsConfirm) {
      setNeedsConfirm(true)
      return
    }
    markSent.mutate(
      {
        template_key: live.template_key,
        channel: channel === "email" ? "email" : "linkedin",
        contact_id: contactId,
        subject: text.subject,
        body: text.body,
        schedule_next: true,
        request_id: requestId,
      },
      {
        onSuccess: (result) => {
          toast.success("Logged as sent", {
            description: result.next_followup_due
              ? `Next follow-up scheduled for ${formatDate(result.next_followup_due)}.`
              : "Added to the timeline.",
          })
          onDone()
        },
        onError: (error) =>
          toast.error(error instanceof ApiError ? error.message : "Couldn't record that."),
      },
    )
  }

  if (suggestions.isLoading || templates.isLoading) return <Skeleton className="h-72 w-full" />
  const stop = advice?.suggestions.find((s) => s.kind === "stop")
  const addContact = advice?.suggestions.find((s) => s.kind === "add_contact")
  const dueKeys = new Set(
    advice?.suggestions.filter((s) => s.kind === "send" && s.due).map((s) => s.template_key),
  )

  return (
    <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
      <TemplateList
        templates={all}
        selected={templateKey}
        dueKeys={dueKeys}
        onPick={pick}
        reasons={Object.fromEntries(
          (advice?.suggestions ?? []).flatMap((s) =>
            s.template_key ? [[s.template_key, s.reason] as const] : [],
          ),
        )}
      />
      <div className="min-w-0 space-y-4">
        {stop ? (
          <p
            role="status"
            className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm"
          >
            {stop.reason}
          </p>
        ) : null}
        {addContact ? (
          <p role="status" className="rounded-lg border p-3 text-sm text-muted-foreground">
            {addContact.reason}
          </p>
        ) : null}
        {template ? (
          <div className="flex flex-wrap items-center gap-2">
            {channels.map((c) => (
              <Button
                key={c}
                size="sm"
                variant={c === channel ? "default" : "outline"}
                onClick={() => {
                  setChannel(c)
                  setDraft(null)
                  setNeedsConfirm(false)
                }}
              >
                {CHANNEL_LABELS[c]}
              </Button>
            ))}
            {advice && advice.contacts.length > 0 ? (
              <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
                To
                <select
                  aria-label="Send to"
                  className="h-8 rounded-md border bg-background px-2 text-sm text-foreground"
                  value={contactId ?? ""}
                  onChange={(e) => {
                    setContact(e.target.value === "" ? null : Number(e.target.value))
                    setDraft(null)
                  }}
                >
                  <option value="">(nobody yet)</option>
                  {advice.contacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                      {c.last_messaged_days !== null
                        ? `, messaged ${c.last_messaged_days}d ago`
                        : ""}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
        ) : null}

        {!text ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <>
            <div className="text-xs text-muted-foreground">
              From <span className="font-mono">{live?.from_email}</span>
              {live?.to ? (
                <>
                  {" "}
                  · To <span className="font-mono">{live.to}</span>
                </>
              ) : null}
              {live?.edited ? (
                <Badge variant="outline" className="ml-2">
                  Your version
                </Badge>
              ) : null}
            </div>
            {text.subject !== null ? (
              <Input
                aria-label="Subject"
                value={text.subject}
                maxLength={200}
                onChange={(e) => edit({ subject: e.target.value })}
              />
            ) : null}
            <Textarea
              aria-label="Message"
              rows={12}
              value={text.body}
              maxLength={3000}
              onChange={(e) => edit({ body: e.target.value })}
              className="font-sans"
            />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>
                {text.body.length}
                {live?.char_limit ? `/${live.char_limit}` : ""} characters
              </span>
              <span className="flex gap-2">
                {undo ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setDraft({ key, ...undo })
                      setUndo(null)
                    }}
                  >
                    <Undo2 /> Undo rewrite
                  </Button>
                ) : null}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="outline" disabled={polish.isPending}>
                      {polish.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}{" "}
                      Improve with AI
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {POLISH.map((p) => (
                      <DropdownMenuItem key={p.value} onSelect={() => runPolish(p.value)}>
                        {p.label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </span>
            </div>

            {uniqueGaps.length > 0 ? <GapFields gaps={uniqueGaps} onFill={fill} /> : null}

            {live?.warnings
              .filter((w) => !w.startsWith("Fill in"))
              .map((w) => (
                <p
                  key={w}
                  className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300"
                >
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> {w}
                </p>
              ))}
            {live?.attach ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Paperclip className="size-4" aria-hidden /> Attach your{" "}
                <Link to="/contacts?tab=resumes" className="font-medium text-foreground underline">
                  {live.attach.label}
                </Link>{" "}
                resume as a PDF
                {live.attach.score !== null ? ` (${live.attach.score}/100 fit for this job)` : ""}.
                Links can't attach files.
              </p>
            ) : null}
            {live && live.tips.length > 0 ? (
              <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                {live.tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            ) : null}

            <div className="flex flex-wrap items-center gap-2 border-t pt-4">
              {channel === "email" ? (
                <>
                  <Button onClick={() => void openEmail()}>
                    <Mail /> Open in email
                  </Button>
                  <Button variant="outline" onClick={openGmail}>
                    <ExternalLink /> Gmail
                  </Button>
                </>
              ) : (
                <Button onClick={() => void openLinkedIn()}>
                  <Users /> Copy and open LinkedIn
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => void copyText().then((ok) => ok && toast.success("Copied"))}
              >
                <Copy /> Copy
              </Button>
              <Button
                className={cn("ml-auto")}
                variant={needsConfirm ? "destructive" : "secondary"}
                onClick={sent}
                disabled={markSent.isPending}
              >
                {markSent.isPending ? <Loader2 className="animate-spin" /> : <Check />}
                {needsConfirm ? "Mark sent anyway" : "I sent it"}
              </Button>
            </div>
            {needsConfirm ? (
              <p role="alert" className="text-sm text-destructive">
                This still has highlighted gaps like [[{uniqueGaps[0]}]]. Fill them in, or confirm
                to record it as sent anyway.
              </p>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}

function GapFields({
  gaps,
  onFill,
}: {
  gaps: string[]
  onFill: (label: string, value: string) => void
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  return (
    <fieldset className="space-y-2 rounded-lg border border-dashed p-3">
      <legend className="px-1 text-xs font-medium text-muted-foreground">Fill in the gaps</legend>
      {gaps.map((gap) => (
        <form
          key={gap}
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            const value = (values[gap] ?? "").trim()
            if (value) onFill(gap, value)
          }}
        >
          <label className="w-48 shrink-0 text-sm" htmlFor={`gap-${gap}`}>
            {gap}
          </label>
          <Input
            id={`gap-${gap}`}
            value={values[gap] ?? ""}
            maxLength={200}
            onChange={(e) => setValues((v) => ({ ...v, [gap]: e.target.value }))}
          />
          <Button type="submit" size="sm" variant="outline" disabled={!(values[gap] ?? "").trim()}>
            Insert
          </Button>
        </form>
      ))}
    </fieldset>
  )
}

function TemplateList({
  templates,
  selected,
  dueKeys,
  reasons,
  onPick,
}: {
  templates: MessageTemplate[]
  selected: string | null
  dueKeys: Set<string | null>
  reasons: Record<string, string>
  onPick: (key: string) => void
}) {
  const groups = new Map<string, MessageTemplate[]>()
  for (const t of templates) {
    if (t.archived) continue
    groups.set(t.group_label, [...(groups.get(t.group_label) ?? []), t])
  }
  return (
    <nav aria-label="Templates" className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
      {[...groups.entries()].map(([label, items]) => (
        <div key={label} className="space-y-1">
          <p className="px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          {items.map((t) => (
            <button
              key={t.key}
              type="button"
              aria-pressed={t.key === selected}
              onClick={() => onPick(t.key)}
              className={cn(
                "w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                t.key === selected && "bg-muted font-medium",
              )}
            >
              <span className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate">{t.name}</span>
                {dueKeys.has(t.key) ? <Badge variant="secondary">Next</Badge> : null}
              </span>
              {reasons[t.key] ? (
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  {reasons[t.key]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ))}
    </nav>
  )
}

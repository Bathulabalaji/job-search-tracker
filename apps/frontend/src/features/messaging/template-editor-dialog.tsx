import { useState } from "react"
import { toast } from "sonner"

import {
  useCreateTemplate,
  useUpdateTemplate,
  type MessageTemplate,
  type OutreachChannel,
  type TemplateVariant,
} from "@/api/messaging"
import { ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

/** Fields a template may use; the server rejects any other name. */
export const MESSAGE_FIELDS = [
  "recipient_first",
  "company",
  "role",
  "my_name",
  "my_first_name",
  "headline",
  "proof_point",
  "bridge",
  "skills",
  "applied_when",
  "signature",
  "notice_period",
  "current_ctc",
  "expected_ctc",
  "my_location",
  "talking_point",
  "new_update",
  "availability",
  "decision_date",
  "round_label",
] as const // fmt: skip

const CHANNELS: { value: OutreachChannel; label: string }[] = [
  { value: "email", label: "Email" },
  { value: "linkedin", label: "LinkedIn message" },
  { value: "linkedin_note", label: "Connection note (300 characters)" },
]

export type EditTarget =
  | { mode: "new" }
  | { mode: "edit-custom"; template: MessageTemplate; variant: TemplateVariant }
  | { mode: "edit-system"; template: MessageTemplate; variant: TemplateVariant }

export function TemplateEditorDialog({
  target,
  onClose,
}: {
  target: EditTarget | null
  onClose: () => void
}) {
  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        {target ? (
          <Editor
            key={target.mode + ("template" in target ? target.template.key : "")}
            target={target}
            onClose={onClose}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function Editor({ target, onClose }: { target: EditTarget; onClose: () => void }) {
  const create = useCreateTemplate()
  const update = useUpdateTemplate()
  const variant = target.mode === "new" ? null : target.variant
  const [name, setName] = useState(target.mode === "new" ? "" : target.template.name)
  const [channel, setChannel] = useState<OutreachChannel>(variant?.channel ?? "email")
  const [subject, setSubject] = useState(variant?.subject ?? "")
  const [body, setBody] = useState(variant?.body ?? "")
  const [error, setError] = useState<string | null>(null)
  const pending = create.isPending || update.isPending

  const fail = (e: Error) => setError(e instanceof ApiError ? e.message : "Could not save.")
  const done = () => {
    toast.success("Template saved")
    onClose()
  }

  const save = () => {
    setError(null)
    const subj = channel === "email" ? subject.trim() : null
    if (target.mode === "edit-custom" && variant?.template_id) {
      update.mutate(
        { id: variant.template_id, patch: { name: name.trim(), subject: subj, body } },
        { onSuccess: done, onError: fail },
      )
    } else if (target.mode === "edit-system" && variant?.template_id) {
      update.mutate(
        { id: variant.template_id, patch: { subject: subj, body } },
        { onSuccess: done, onError: fail },
      )
    } else {
      create.mutate(
        {
          name: name.trim(),
          channel,
          subject: subj,
          body,
          ...(target.mode === "edit-system"
            ? { base_key: target.template.key.replace("sys:", "") }
            : {}),
        },
        { onSuccess: done, onError: fail },
      )
    }
  }

  const title =
    target.mode === "new"
      ? "New template"
      : target.mode === "edit-system"
        ? `Edit your copy of “${target.template.name}”`
        : "Edit template"

  return (
    <>
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>
          Use fields like {"{{recipient_first}}"} to fill in details. Leave a field empty in your
          profile and the draft shows a gap to fill in. Wrap a line in {"{{?proof_point}}"} …{" "}
          {"{{/}}"}
          to drop it when that field is empty.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4">
        {target.mode !== "edit-system" ? (
          <div className="space-y-1.5">
            <Label htmlFor="tpl-name">Name</Label>
            <Input
              id="tpl-name"
              value={name}
              maxLength={120}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
        ) : null}
        {target.mode === "new" ? (
          <div className="space-y-1.5">
            <Label htmlFor="tpl-channel">Channel</Label>
            <select
              id="tpl-channel"
              className="h-9 w-full rounded-md border bg-background px-2 text-sm"
              value={channel}
              onChange={(e) => setChannel(e.target.value as OutreachChannel)}
            >
              {CHANNELS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {channel === "email" ? (
          <div className="space-y-1.5">
            <Label htmlFor="tpl-subject">Subject</Label>
            <Input
              id="tpl-subject"
              value={subject}
              maxLength={200}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
        ) : null}
        <div className="space-y-1.5">
          <Label htmlFor="tpl-body">Message</Label>
          <Textarea
            id="tpl-body"
            rows={10}
            value={body}
            maxLength={3000}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1" aria-label="Insert a field">
          {MESSAGE_FIELDS.map((field) => (
            <Button
              key={field}
              type="button"
              size="sm"
              variant="outline"
              className="h-6 px-2 font-mono text-xs"
              onClick={() => setBody((b) => `${b}{{${field}}}`)}
            >
              {field}
            </Button>
          ))}
        </div>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </div>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={save}
          disabled={pending || !body.trim() || (target.mode !== "edit-system" && !name.trim())}
        >
          {pending ? "Saving…" : "Save"}
        </Button>
      </DialogFooter>
    </>
  )
}

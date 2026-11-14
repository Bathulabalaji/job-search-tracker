import { FilePlus2, Pencil, RotateCcw, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import {
  useDeleteTemplate,
  useTemplates,
  type MessageTemplate,
  type TemplateVariant,
} from "@/api/messaging"
import { ErrorState } from "@/components/common/error-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { TemplateEditorDialog, type EditTarget } from "./template-editor-dialog"

const CHANNEL_LABELS = {
  email: "Email",
  linkedin: "LinkedIn",
  linkedin_note: "Connection note",
} as const

/** The message library: built-in templates (editable as your own copy) and your own. */
export function TemplatesTab() {
  const templates = useTemplates()
  const remove = useDeleteTemplate()
  const [editing, setEditing] = useState<EditTarget | null>(null)

  if (templates.isLoading) return <Skeleton className="h-64 w-full" />
  if (templates.isError || !templates.data)
    return (
      <ErrorState
        message="Couldn't load your templates."
        onRetry={() => void templates.refetch()}
      />
    )

  const groups = new Map<string, MessageTemplate[]>()
  for (const t of templates.data)
    groups.set(t.group_label, [...(groups.get(t.group_label) ?? []), t])

  const reset = (variant: TemplateVariant) => {
    if (variant.template_id === null) return
    remove.mutate(variant.template_id, {
      onSuccess: () => toast.success("Restored the original"),
      onError: () => toast.error("Couldn't restore it."),
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-muted-foreground">
          Ready-made messages for each stage of a job search. Edit any of them and your version is
          used from then on; you can always restore the original.
        </p>
        <Button onClick={() => setEditing({ mode: "new" })}>
          <FilePlus2 /> New template
        </Button>
      </div>
      {[...groups.entries()].map(([label, items]) => (
        <section key={label} aria-label={label} className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">{label}</h2>
          <ul className="divide-y rounded-lg border">
            {items.map((t) => (
              <li key={t.key} className="space-y-2 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{t.name}</span>
                  {t.india_only ? <Badge variant="outline">India</Badge> : null}
                  {t.archived ? <Badge variant="outline">Archived</Badge> : null}
                </div>
                {t.summary ? <p className="text-sm text-muted-foreground">{t.summary}</p> : null}
                <ul className="flex flex-wrap gap-2">
                  {t.variants.map((v) => (
                    <li
                      key={v.channel}
                      className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs"
                    >
                      <span>{CHANNEL_LABELS[v.channel]}</span>
                      {v.edited ? <Badge variant="secondary">Your version</Badge> : null}
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-6"
                        aria-label={`Edit ${t.name} (${CHANNEL_LABELS[v.channel]})`}
                        onClick={() =>
                          setEditing({
                            mode: t.source === "custom" ? "edit-custom" : "edit-system",
                            template: t,
                            variant: v,
                          })
                        }
                      >
                        <Pencil />
                      </Button>
                      {t.source === "system" && v.edited ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-6"
                          aria-label={`Restore the original ${t.name} (${CHANNEL_LABELS[v.channel]})`}
                          onClick={() => reset(v)}
                        >
                          <RotateCcw />
                        </Button>
                      ) : null}
                      {t.source === "custom" && v.template_id !== null ? (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-6"
                          aria-label={`Delete ${t.name}`}
                          onClick={() => {
                            if (window.confirm(`Delete “${t.name}”?`)) reset(v)
                          }}
                        >
                          <Trash2 />
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <TemplateEditorDialog target={editing} onClose={() => setEditing(null)} />
    </div>
  )
}

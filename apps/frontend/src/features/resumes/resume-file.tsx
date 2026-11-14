import { ExternalLink, FileUp, Loader2, RefreshCw, Trash2 } from "lucide-react"
import { useRef, useState } from "react"
import { toast } from "sonner"

import { ApiError, retryMessage } from "@/api/client"
import {
  getResumeDocumentUrl,
  useDeleteResumeDocument,
  useReindexResume,
  useUploadResumeDocument,
} from "@/api/resumes"
import type { Resume, ResumeDocument } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const MAX_MB = 5

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.status === 429 ? retryMessage(error) : error.message
  return "Something went wrong."
}

function statusOf(doc: ResumeDocument): { label: string; tone: "ok" | "wait" | "bad" } {
  if (doc.text_status === "failed" || doc.embed_status === "failed")
    return { label: "Failed", tone: "bad" }
  if (doc.embed_status === "ready") return { label: "Indexed", tone: "ok" }
  if (doc.processing_error) return { label: "Indexing paused", tone: "wait" }
  return { label: "Indexing…", tone: "wait" }
}

/**
 * The file attached to a resume: upload it, see how indexing is going, open or remove it.
 * Shown in the resumes table and in the small-screen cards.
 */
export function ResumeFile({ resume, compact = false }: { resume: Resume; compact?: boolean }) {
  const uploadDoc = useUploadResumeDocument()
  const removeDoc = useDeleteResumeDocument()
  const reindex = useReindexResume()
  const input = useRef<HTMLInputElement>(null)
  const [opening, setOpening] = useState(false)
  const doc = resume.document
  const busy = uploadDoc.isPending || removeDoc.isPending || reindex.isPending

  const pick = () => input.current?.click()
  const onFile = (file: File | undefined) => {
    if (input.current) input.current.value = ""
    if (!file) return
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`That file is over ${MAX_MB} MB.`)
      return
    }
    uploadDoc.mutate(
      { id: resume.id, file },
      {
        onSuccess: () =>
          toast.success("Resume uploaded", { description: "Indexing in the background." }),
        onError: (e) => toast.error("Could not upload", { description: describe(e) }),
      },
    )
  }
  const open = async () => {
    setOpening(true)
    try {
      const { url } = await getResumeDocumentUrl(resume.id)
      window.open(url, "_blank", "noopener")
    } catch (e) {
      toast.error("Could not open the file", { description: describe(e) })
    } finally {
      setOpening(false)
    }
  }

  const picker = (
    <input
      ref={input}
      type="file"
      accept="application/pdf,.pdf"
      className="sr-only"
      aria-label={`Choose a PDF for ${resume.label}`}
      onChange={(e) => onFile(e.target.files?.[0])}
    />
  )

  if (!doc) {
    return (
      <div className="flex items-center gap-2">
        {picker}
        <Button variant="outline" size="sm" onClick={pick} disabled={busy}>
          {uploadDoc.isPending ? <Loader2 className="animate-spin" /> : <FileUp />}
          Upload PDF
        </Button>
      </div>
    )
  }

  const status = statusOf(doc)
  return (
    <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-1", compact && "text-xs")}>
      {picker}
      <span className="max-w-48 truncate font-mono text-xs" title={doc.file_name ?? undefined}>
        {doc.file_name}
      </span>
      <Badge
        variant={status.tone === "ok" ? "secondary" : "outline"}
        className={cn(
          status.tone === "bad" && "border-destructive/40 text-destructive",
          status.tone === "wait" && "text-muted-foreground",
        )}
        title={doc.processing_error ?? undefined}
      >
        {status.tone === "wait" && !doc.processing_error ? (
          <Loader2 className="mr-1 size-3 animate-spin" aria-hidden />
        ) : null}
        {status.label}
      </Badge>
      <span className="flex items-center">
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Open ${doc.file_name ?? "file"}`}
          onClick={() => void open()}
          disabled={opening}
        >
          {opening ? <Loader2 className="animate-spin" /> : <ExternalLink />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Replace file for ${resume.label}`}
          onClick={pick}
          disabled={busy}
        >
          <FileUp />
        </Button>
        {status.tone !== "ok" ? (
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Retry indexing ${resume.label}`}
            disabled={busy}
            onClick={() =>
              reindex.mutate(resume.id, {
                onError: (e) => toast.error("Could not re-index", { description: describe(e) }),
              })
            }
          >
            <RefreshCw className={cn(reindex.isPending && "animate-spin")} />
          </Button>
        ) : null}
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Remove file from ${resume.label}`}
          disabled={busy}
          onClick={() =>
            removeDoc.mutate(resume.id, {
              onSuccess: () => toast.success("File removed"),
              onError: (e) => toast.error("Could not remove", { description: describe(e) }),
            })
          }
        >
          <Trash2 />
        </Button>
      </span>
    </div>
  )
}

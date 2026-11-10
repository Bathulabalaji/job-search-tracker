import { FileText, Pencil, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { useDeleteResume, useResumes } from "@/api/resumes"
import type { Resume } from "@/api/types"
import { ConfirmDeleteDialog } from "@/components/common/confirm-delete-dialog"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { SearchBox } from "@/components/common/search-box"
import { useDebouncedValue } from "@/lib/use-debounced-value"
import { ResumeDialog } from "./resume-dialog"

/** '3' -> 'v3', but leave 'v3' and 'draft-2' alone. */
function versionLabel(version: string): string {
  return /^\d/.test(version) ? `v${version}` : version
}

export function ResumesTab() {
  const [search, setSearch] = useState("")
  const q = useDebouncedValue(search.trim(), 250)
  const { data, isPending, isError, error, refetch } = useResumes(q)
  const remove = useDeleteResume()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Resume | null>(null)
  const [deleting, setDeleting] = useState<Resume | null>(null)

  const openAdd = () => {
    setEditing(null)
    setDialogOpen(true)
  }
  const openEdit = (resume: Resume) => {
    setEditing(resume)
    setDialogOpen(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SearchBox value={search} onChange={setSearch} label="Search resumes" />
        <Button onClick={openAdd}>
          <Plus />
          Add resume
        </Button>
      </div>

      {isPending ? (
        <Skeleton className="h-48" aria-busy="true" aria-label="Loading resumes" />
      ) : null}
      {isError ? <ErrorState message={error.message} onRetry={() => void refetch()} /> : null}

      {data && data.length === 0 ? (
        q ? (
          <EmptyState
            icon={FileText}
            title="No resumes match"
            description={`Nothing found for “${q}”.`}
          />
        ) : (
          <EmptyState
            icon={FileText}
            title="No resumes yet"
            description="Record each version you send (label, focus, file name) so you know which one went where."
            action={<Button onClick={openAdd}>Add your first resume</Button>}
          />
        )
      ) : null}

      {data && data.length > 0 ? (
        <>
          <ul className="space-y-3 md:hidden">
            {data.map((resume) => (
              <li key={resume.id} className="space-y-2 rounded-xl border bg-card p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-medium">
                      {resume.label}
                      <Badge variant="secondary" className="font-mono">
                        {versionLabel(resume.version)}
                      </Badge>
                    </p>
                    {resume.focus ? (
                      <p className="text-sm text-muted-foreground">{resume.focus}</p>
                    ) : null}
                  </div>
                  <div className="-mr-2 -mt-1 flex shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit ${resume.label}`}
                      onClick={() => openEdit(resume)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${resume.label}`}
                      onClick={() => setDeleting(resume)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
                {resume.file_name ? (
                  <p className="break-all font-mono text-xs">{resume.file_name}</p>
                ) : null}
                {resume.notes ? (
                  <p className="text-sm text-muted-foreground">{resume.notes}</p>
                ) : null}
              </li>
            ))}
          </ul>
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Focus</TableHead>
                  <TableHead>File name</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Notes</TableHead>
                  <TableHead className="w-24">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((resume) => (
                  <TableRow key={resume.id}>
                    <TableCell className="font-medium">{resume.label}</TableCell>
                    <TableCell className="text-muted-foreground">{resume.focus ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{resume.file_name ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono">
                        {versionLabel(resume.version)}
                      </Badge>
                    </TableCell>
                    <TableCell
                      className="max-w-64 truncate text-muted-foreground"
                      title={resume.notes ?? undefined}
                    >
                      {resume.notes ?? "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit ${resume.label}`}
                          onClick={() => openEdit(resume)}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${resume.label}`}
                          onClick={() => setDeleting(resume)}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      ) : null}

      <ResumeDialog open={dialogOpen} onOpenChange={setDialogOpen} resume={editing} />
      <ConfirmDeleteDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete ${deleting?.label ?? "resume"}?`}
        description="Only this record is removed. Your actual file is not touched."
        pending={remove.isPending}
        onConfirm={() => {
          if (!deleting) return
          remove.mutate(deleting.id, {
            onSuccess: () => {
              toast.success("Resume deleted")
              setDeleting(null)
            },
            onError: (e) => toast.error("Could not delete", { description: e.message }),
          })
        }}
      />
    </div>
  )
}

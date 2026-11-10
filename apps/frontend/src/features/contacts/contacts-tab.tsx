import { ExternalLink, Pencil, Plus, Trash2, Users } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { useContactsList, useDeleteContact } from "@/api/contacts"
import { useOpportunities } from "@/api/opportunities"
import { CONTACT_ROLES, type Contact } from "@/api/types"
import { ConfirmDeleteDialog } from "@/components/common/confirm-delete-dialog"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorState } from "@/components/common/error-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
import { titleCase } from "@/lib/format"
import { useDebouncedValue } from "@/lib/use-debounced-value"
import { ContactDialog } from "./contact-dialog"

const ALL = "all"

export function ContactsTab() {
  const [search, setSearch] = useState("")
  const [role, setRole] = useState(ALL)
  const q = useDebouncedValue(search.trim(), 250)
  const filters = useMemo(() => {
    const result: { q?: string; role?: string } = {}
    if (q) result.q = q
    if (role !== ALL) result.role = role
    return result
  }, [q, role])
  const hasFilters = Object.keys(filters).length > 0

  const { data, isPending, isError, error, refetch } = useContactsList(filters)
  const opportunities = useOpportunities({})
  const remove = useDeleteContact()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Contact | null>(null)
  const [deleting, setDeleting] = useState<Contact | null>(null)

  const opportunityNames = useMemo(
    () => new Map((opportunities.data ?? []).map((o) => [o.id, `${o.company} · ${o.role}`])),
    [opportunities.data],
  )

  const openAdd = () => {
    setEditing(null)
    setDialogOpen(true)
  }
  const openEdit = (contact: Contact) => {
    setEditing(contact)
    setDialogOpen(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
          <SearchBox value={search} onChange={setSearch} label="Search name, company or email" />
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="w-full sm:w-40" aria-label="Filter by role">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All roles</SelectItem>
              {CONTACT_ROLES.map((r) => (
                <SelectItem key={r} value={r}>
                  {titleCase(r)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={openAdd}>
          <Plus />
          Add contact
        </Button>
      </div>

      {isPending ? (
        <Skeleton className="h-48" aria-busy="true" aria-label="Loading contacts" />
      ) : null}
      {isError ? <ErrorState message={error.message} onRetry={() => void refetch()} /> : null}

      {data && data.length === 0 ? (
        hasFilters ? (
          <EmptyState
            icon={Users}
            title="No contacts match"
            description="Try a different search or clear the role filter."
          />
        ) : (
          <EmptyState
            icon={Users}
            title="No contacts yet"
            description="Keep recruiters, hiring managers and referrers in one place, linked to the roles they are helping with."
            action={<Button onClick={openAdd}>Add your first contact</Button>}
          />
        )
      ) : null}

      {data && data.length > 0 ? (
        <>
          {/* Phones: stacked cards. A seven-column table does not fit and hides actions off-screen. */}
          <ul className="space-y-3 md:hidden">
            {data.map((contact) => (
              <li key={contact.id} className="space-y-2 rounded-xl border bg-card p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium">{contact.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {[contact.company, titleCase(contact.role)].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="-mr-2 -mt-1 flex shrink-0">
                    {contact.linkedin_url ? (
                      <Button variant="ghost" size="icon" asChild>
                        <a
                          href={contact.linkedin_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          aria-label={`Open ${contact.name}'s LinkedIn profile`}
                        >
                          <ExternalLink />
                        </a>
                      </Button>
                    ) : null}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Edit ${contact.name}`}
                      onClick={() => openEdit(contact)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${contact.name}`}
                      onClick={() => setDeleting(contact)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
                <dl className="space-y-1 text-sm">
                  {contact.email ? (
                    <div className="flex gap-2">
                      <dt className="w-16 shrink-0 text-muted-foreground">Email</dt>
                      <dd className="min-w-0 break-all">
                        <a className="hover:underline" href={`mailto:${contact.email}`}>
                          {contact.email}
                        </a>
                      </dd>
                    </div>
                  ) : null}
                  {contact.phone ? (
                    <div className="flex gap-2">
                      <dt className="w-16 shrink-0 text-muted-foreground">Phone</dt>
                      <dd className="font-mono text-xs leading-5">{contact.phone}</dd>
                    </div>
                  ) : null}
                  {contact.opportunity_id !== null ? (
                    <div className="flex gap-2">
                      <dt className="w-16 shrink-0 text-muted-foreground">Role</dt>
                      <dd className="min-w-0">
                        <Link
                          to={`/opportunities/${contact.opportunity_id}`}
                          className="inline-block py-0.5 hover:underline"
                        >
                          {opportunityNames.get(contact.opportunity_id) ??
                            `#${contact.opportunity_id}`}
                        </Link>
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {contact.notes ? (
                  <p className="text-sm text-muted-foreground">{contact.notes}</p>
                ) : null}
              </li>
            ))}
          </ul>
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Opportunity</TableHead>
                  <TableHead className="w-28">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((contact) => (
                  <TableRow key={contact.id}>
                    <TableCell className="font-medium">
                      {contact.name}
                      {contact.notes ? (
                        <span
                          className="block max-w-56 truncate text-xs font-normal text-muted-foreground"
                          title={contact.notes}
                        >
                          {contact.notes}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-normal">
                        {titleCase(contact.role)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {contact.company ?? "—"}
                    </TableCell>
                    <TableCell>
                      {contact.email ? (
                        <a className="hover:underline" href={`mailto:${contact.email}`}>
                          {contact.email}
                        </a>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{contact.phone ?? "—"}</TableCell>
                    <TableCell>
                      {contact.opportunity_id === null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <Link
                          to={`/opportunities/${contact.opportunity_id}`}
                          className="rounded-sm hover:underline"
                        >
                          {opportunityNames.get(contact.opportunity_id) ??
                            `#${contact.opportunity_id}`}
                        </Link>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end">
                        {contact.linkedin_url ? (
                          <Button variant="ghost" size="icon" asChild>
                            <a
                              href={contact.linkedin_url}
                              target="_blank"
                              rel="noreferrer noopener"
                              aria-label={`Open ${contact.name}'s LinkedIn profile`}
                            >
                              <ExternalLink />
                            </a>
                          </Button>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit ${contact.name}`}
                          onClick={() => openEdit(contact)}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${contact.name}`}
                          onClick={() => setDeleting(contact)}
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

      <ContactDialog open={dialogOpen} onOpenChange={setDialogOpen} contact={editing} />
      <ConfirmDeleteDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete ${deleting?.name ?? "contact"}?`}
        description="Their past interactions stay on the timeline, unlinked from this contact."
        pending={remove.isPending}
        onConfirm={() => {
          if (!deleting) return
          remove.mutate(deleting.id, {
            onSuccess: () => {
              toast.success("Contact deleted")
              setDeleting(null)
            },
            onError: (e) => toast.error("Could not delete", { description: e.message }),
          })
        }}
      />
    </div>
  )
}

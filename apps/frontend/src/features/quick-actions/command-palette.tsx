import { Briefcase, MessageSquarePlus, Plus } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { useOpportunities } from "@/api/opportunities"
import { NAV_ITEMS } from "@/components/layout/nav"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { STAGE_LABELS } from "@/lib/format"

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAddOpportunity: () => void
  onLogInteraction: () => void
}

export function CommandPalette({
  open,
  onOpenChange,
  onAddOpportunity,
  onLogInteraction,
}: CommandPaletteProps) {
  const navigate = useNavigate()
  const opportunities = useOpportunities({}, open)

  // Close first so focus returns before the next dialog opens.
  const run = (action: () => void) => () => {
    onOpenChange(false)
    action()
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Command palette"
      description="Jump to a page, add an opportunity or log an interaction."
    >
      <CommandInput placeholder="Type a command or search opportunities…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Quick actions">
          <CommandItem onSelect={run(onAddOpportunity)} keywords={["new", "create", "quick add"]}>
            <Plus />
            Add opportunity
          </CommandItem>
          <CommandItem onSelect={run(onLogInteraction)} keywords={["call", "email", "message", "note"]}>
            <MessageSquarePlus />
            Log interaction
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Go to">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <CommandItem key={to} onSelect={run(() => void navigate(to))} keywords={["page", "open"]}>
              <Icon />
              {label}
            </CommandItem>
          ))}
        </CommandGroup>

        {opportunities.data && opportunities.data.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Opportunities">
              {opportunities.data.map((o) => (
                <CommandItem
                  key={o.id}
                  value={`${o.company} ${o.role} ${o.id}`}
                  onSelect={run(() => void navigate(`/opportunities/${o.id}`))}
                >
                  <Briefcase />
                  <span className="truncate">
                    {o.company} <span className="text-muted-foreground">· {o.role}</span>
                  </span>
                  <CommandShortcut>{STAGE_LABELS[o.stage]}</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}
      </CommandList>
    </CommandDialog>
  )
}

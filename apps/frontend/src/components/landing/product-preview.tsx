import { CalendarCheck, Flame, Kanban, Search } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * A static, decorative mock of the real app (sample data only). It is hidden from assistive
 * technology because it carries no information the surrounding copy does not.
 */

const COLUMNS: readonly {
  name: string
  tone: string
  cards: readonly { company: string; role: string; days: string; hot?: boolean }[]
}[] = [
  {
    name: "Applied",
    tone: "bg-sky-400",
    cards: [
      { company: "Northwind", role: "Backend Engineer", days: "2d" },
      { company: "Lumen Labs", role: "Python Developer", days: "5d" },
    ],
  },
  {
    name: "Screening",
    tone: "bg-amber-400",
    cards: [{ company: "Helix", role: "FastAPI Engineer", days: "1d", hot: true }],
  },
  {
    name: "Interviewing",
    tone: "bg-violet-400",
    cards: [
      { company: "Orbit", role: "Platform Engineer", days: "Today", hot: true },
      { company: "Acme Cloud", role: "SDE II", days: "3d" },
    ],
  },
  {
    name: "Offer",
    tone: "bg-emerald-400",
    cards: [{ company: "Finch", role: "Senior Backend", days: "Today" }],
  },
]

const BARS = [38, 62, 45, 80, 55, 92, 70]

export function ProductPreview({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border/80 bg-card/80 shadow-2xl shadow-primary/10 ring-1 ring-foreground/5 backdrop-blur",
        className,
      )}
    >
      {/* window chrome */}
      <div className="flex items-center gap-2 border-b border-border/70 bg-muted/40 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-rose-400/80" />
        <span className="size-2.5 rounded-full bg-amber-400/80" />
        <span className="size-2.5 rounded-full bg-emerald-400/80" />
        <div className="mx-auto hidden items-center gap-2 rounded-md border border-border/70 bg-background/60 px-3 py-1 text-xs text-muted-foreground sm:flex">
          <Search className="size-3" />
          Search or jump to…
          <kbd className="ml-6 rounded border border-border bg-muted px-1.5 font-mono text-[10px]">
            ⌘K
          </kbd>
        </div>
        <span className="ml-auto text-[10px] tracking-wide text-muted-foreground uppercase sm:ml-0">
          Sample data
        </span>
      </div>

      <div className="grid gap-px bg-border/60 md:grid-cols-[1fr_15rem]">
        {/* pipeline */}
        <div className="bg-card p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium">
            <Kanban className="size-4 text-primary" />
            Pipeline
            <span className="ml-auto rounded-full bg-primary/15 px-2 py-0.5 font-mono text-[10px] text-primary">
              6 active
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {COLUMNS.map((col, i) => (
              <div
                key={col.name}
                className={cn("space-y-2", i > 1 && "hidden sm:block", i > 1 && "lg:block")}
              >
                <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                  <span className={cn("size-1.5 rounded-full", col.tone)} />
                  {col.name}
                  <span className="ml-auto font-mono">{col.cards.length}</span>
                </div>
                {col.cards.map((card) => (
                  <div
                    key={card.company}
                    className="rounded-lg border border-border/80 bg-background/70 p-2.5 shadow-xs"
                  >
                    <p className="truncate text-xs font-medium">{card.company}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{card.role}</p>
                    <div className="mt-2 flex items-center justify-between">
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 font-mono text-[10px]",
                          card.hot
                            ? "bg-primary/15 text-primary"
                            : "bg-muted text-muted-foreground",
                        )}
                      >
                        {card.days}
                      </span>
                      <span className="size-4 rounded-full bg-gradient-to-br from-primary/60 to-violet-400/60" />
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* today + streak */}
        <div className="space-y-4 bg-card p-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <CalendarCheck className="size-4 text-primary" />
              Today
            </div>
            <ul className="space-y-1.5 text-[11px]">
              {[
                ["Follow up with Helix", "due"],
                ["Interview · Orbit, 4:00 PM", "today"],
                ["Send referral note", "overdue"],
              ].map(([label, tag]) => (
                <li
                  key={label}
                  className="flex items-center gap-2 rounded-md border border-border/70 bg-background/60 px-2 py-1.5"
                >
                  <span className="size-3 shrink-0 rounded-full border border-muted-foreground/50" />
                  <span className="truncate">{label}</span>
                  <span
                    className={cn(
                      "ml-auto rounded px-1 font-mono text-[9px] uppercase",
                      tag === "overdue"
                        ? "bg-destructive/15 text-destructive"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    {tag}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Flame className="size-4 text-amber-400" />
              This week
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                7-day streak
              </span>
            </div>
            <div className="flex h-16 items-end gap-1.5">
              {BARS.map((h, i) => (
                <span
                  key={i}
                  style={{ height: `${h}%` }}
                  className="flex-1 rounded-t bg-gradient-to-t from-primary/30 to-primary"
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

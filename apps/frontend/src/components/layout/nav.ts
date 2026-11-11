import {
  BarChart3,
  BookOpenCheck,
  CalendarCheck,
  ClipboardList,
  Kanban,
  Users,
  type LucideIcon,
} from "lucide-react"

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/today", label: "Today", icon: CalendarCheck },
  { to: "/pipeline", label: "Pipeline", icon: Kanban },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/daily-log", label: "Daily log", icon: ClipboardList },
  { to: "/prep", label: "Prep", icon: BookOpenCheck },
  { to: "/contacts", label: "Contacts & Resumes", icon: Users },
]

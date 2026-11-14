import { BellRing, Command, Kanban, ShieldCheck, Sparkles } from "lucide-react"
import { Link, Outlet } from "react-router-dom"

import { ProductPreview } from "@/components/landing/product-preview"
import { ThemeToggle } from "@/components/layout/theme-toggle"

const BENEFITS = [
  {
    icon: Kanban,
    title: "One pipeline for every application",
    text: "From found to offer, with the next step always visible.",
  },
  {
    icon: BellRing,
    title: "Follow-ups that don't slip",
    text: "Reminders and ready-to-send messages for email and LinkedIn.",
  },
  {
    icon: Sparkles,
    title: "An assistant that knows your search",
    text: "Match resumes to jobs and prepare for interviews.",
  },
] as const

/** Split shell for every signed-out page: brand story on the left (large screens), form on the right. */
export function AuthLayout() {
  return (
    <div className="min-h-dvh bg-background lg:grid lg:grid-cols-2">
      <BrandPanel />

      <div className="relative flex min-h-dvh flex-col px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-8">
        {/* a soft wash of the brand colour behind the form on small screens, where the panel is hidden */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-primary/15 to-transparent lg:hidden"
        />
        <header className="relative mx-auto flex w-full max-w-md items-center justify-between py-2 lg:max-w-lg lg:justify-end">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-md font-semibold tracking-tight lg:hidden"
          >
            <BrandMark />
            Career Command Center
          </Link>
          <ThemeToggle />
        </header>
        <main className="relative mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-6 lg:max-w-lg motion-safe:animate-in motion-safe:duration-500 motion-safe:fade-in motion-safe:slide-in-from-bottom-2 [&_[data-slot=card]]:lg:bg-transparent [&_[data-slot=card]]:lg:shadow-none [&_[data-slot=card]]:lg:ring-0">
          <Outlet />
        </main>
        <p className="relative mx-auto flex w-full max-w-md items-center justify-center gap-1.5 pb-1 text-center text-xs text-muted-foreground lg:max-w-lg">
          <ShieldCheck className="size-3.5" aria-hidden />
          Your search stays private. You send every message yourself.
        </p>
      </div>
    </div>
  )
}

function BrandMark() {
  return (
    <span className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#7B7FFF] to-[#4338CA] text-white shadow-sm">
      <Command className="size-4" aria-hidden />
    </span>
  )
}

/** Decorative and marketing-only: hidden below the lg breakpoint. */
function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden bg-gradient-to-br from-[#7B7FFF] via-[#5B55E6] to-[#3B31B8] text-white lg:flex lg:flex-col">
      {/* glows and a faded dot grid for depth */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -left-24 size-[28rem] rounded-full bg-white/20 blur-3xl" />
        <div className="absolute -right-24 bottom-0 size-[26rem] rounded-full bg-[#1E1B6B]/50 blur-3xl" />
        <div className="absolute inset-0 [background-image:radial-gradient(rgba(255,255,255,0.22)_1px,transparent_1px)] [background-size:24px_24px] [mask-image:linear-gradient(to_bottom,black,transparent_70%)]" />
      </div>

      <div className="relative flex h-full min-h-dvh flex-col gap-10 pt-10 pl-10 xl:pt-14 xl:pl-14">
        <Link
          to="/"
          className="flex w-fit items-center gap-2.5 rounded-md text-lg font-semibold tracking-tight focus-visible:outline-2 focus-visible:outline-white"
        >
          <span className="flex size-9 items-center justify-center rounded-xl bg-white/95 text-[#4338CA] shadow-lg shadow-black/10">
            <Command className="size-5" aria-hidden />
          </span>
          Career Command Center
        </Link>

        <div className="max-w-md space-y-8 pr-10">
          <div className="space-y-3">
            <p className="text-3xl leading-tight font-semibold tracking-tight text-balance xl:text-4xl">
              Run your job search like a project, not a spreadsheet.
            </p>
            <p className="text-base text-white/80">
              Track every application, follow-up and interview in one place.
            </p>
          </div>

          <ul className="space-y-4">
            {BENEFITS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/15 ring-1 ring-white/25">
                  <Icon className="size-4" aria-hidden />
                </span>
                <span>
                  <span className="block text-sm font-medium">{title}</span>
                  <span className="block text-sm text-white/75">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* a sample of the real app, bleeding off the bottom-right corner */}
        <div className="relative mt-auto min-h-0 flex-1">
          <ProductPreview className="absolute top-0 left-0 w-[46rem] max-w-none border-white/20 shadow-2xl shadow-black/30" />
        </div>
      </div>
    </aside>
  )
}

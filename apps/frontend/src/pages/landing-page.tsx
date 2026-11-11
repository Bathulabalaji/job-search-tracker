import {
  ArrowRight,
  BarChart3,
  BellRing,
  BookOpenCheck,
  CalendarCheck,
  Check,
  ClipboardList,
  Command,
  Kanban,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react"
import { Link, Navigate } from "react-router-dom"

import { ProductPreview } from "@/components/landing/product-preview"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/features/auth/auth-context"
import { PRIVACY_URL, TERMS_URL } from "@/lib/env"
import { cn } from "@/lib/utils"

/** "/" shows the landing page to visitors and sends signed-in users straight to their day. */
export function HomeRoute() {
  const { state } = useAuth()
  if (state.status === "authenticated") return <Navigate to="/today" replace />
  return <LandingPage />
}

const COPYRIGHT_YEAR = new Date().getFullYear()

const NAV_LINKS = [
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#privacy", label: "Privacy" },
] as const

const FACTS = [
  { value: "10", label: "pipeline stages, from found to accepted" },
  { value: "2 days", label: "until a follow-up is created for you" },
  { value: "21 days", label: "of silence before we suggest ghosted" },
  { value: "⌘K", label: "to add or jump anywhere" },
] as const

interface Feature {
  icon: LucideIcon
  title: string
  body: string
  className?: string
}

const FEATURES: readonly Feature[] = [
  {
    icon: Kanban,
    title: "A pipeline you can drag",
    body: "Every opportunity on one kanban board. Drop a card into a new stage and the move is logged on its timeline. Works with a mouse, a finger or just the keyboard.",
    className: "lg:col-span-2",
  },
  {
    icon: CalendarCheck,
    title: "Start each day knowing what matters",
    body: "Overdue and due follow-ups, today's interviews and your top next actions, all on one screen. Mark done or snooze in a click.",
  },
  {
    icon: BellRing,
    title: "Follow-ups that create themselves",
    body: "Apply or reach screening and a follow-up appears, due in two working days. Silent for three weeks? You get a gentle nudge to mark it ghosted.",
  },
  {
    icon: BarChart3,
    title: "See what is actually working",
    body: "Weekly targets against real numbers, your funnel, response rate by source and applications per day.",
    className: "lg:col-span-2",
  },
  {
    icon: ClipboardList,
    title: "A daily log that takes ten seconds",
    body: "Just numbers: applications, messages, referrals, problems, mocks. Keep the streak going.",
  },
  {
    icon: BookOpenCheck,
    title: "Interview prep, tracked",
    body: "A topic checklist with confidence ratings and progress bars, so you know where to spend tomorrow.",
    className: "lg:col-span-2",
  },
]

const STEPS = [
  {
    title: "Capture every role",
    body: "Press ⌘K, type a company and role, and it is in your pipeline. Add the JD, contacts and notes when you have time.",
  },
  {
    title: "Move it forward",
    body: "Drag cards between stages. Calls, emails and nudges become a timeline, and follow-ups are scheduled for you.",
  },
  {
    title: "Review and adjust",
    body: "Check your weekly scorecard, see which sources reply, and put effort where it pays off.",
  },
] as const

const PRIVACY_POINTS: readonly { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: UserRoundCheck,
    title: "Your data is yours alone",
    body: "Every record is tied to your account. Nobody else can read it.",
  },
  {
    icon: LockKeyhole,
    title: "Hardened sign-in",
    body: "Passwords are hashed with Argon2id. Sessions live in HttpOnly cookies that scripts cannot read.",
  },
  {
    icon: KeyRound,
    title: "Google or email",
    body: "Continue with Google or use email and password, with verified addresses and safe password resets.",
  },
  {
    icon: ShieldCheck,
    title: "Nothing sensitive stored",
    body: "No government IDs, bank details or resume files. Just the job-search notes you choose to add.",
  },
]

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-md font-semibold tracking-tight">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-lg shadow-primary/30">
        <Command className="size-4" aria-hidden />
      </span>
      Jobs Tracker
    </Link>
  )
}

function SectionHeading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string
  title: string
  body?: string
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-sm font-medium tracking-wide text-primary uppercase">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      {body ? <p className="mt-4 text-pretty text-muted-foreground">{body}</p> : null}
    </div>
  )
}

export function LandingPage() {
  return (
    <div className="relative min-h-dvh overflow-x-clip bg-background text-foreground">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      {/* ambient glow */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-[48rem]">
        <div className="absolute top-[-12rem] left-1/2 size-[44rem] -translate-x-1/2 rounded-full bg-primary/25 blur-[120px] motion-safe:animate-pulse [animation-duration:8s]" />
        <div className="absolute top-24 -right-32 size-[26rem] rounded-full bg-violet-500/15 blur-[110px]" />
        <div className="absolute inset-0 opacity-[0.35] [background-image:linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] [background-size:56px_56px] [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_70%)]" />
      </div>

      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 pt-[env(safe-area-inset-top)] backdrop-blur-lg">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="ml-8 hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="rounded text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1.5">
            <ThemeToggle />
            <Button asChild variant="ghost" className="hidden sm:inline-flex">
              <Link to="/login">Sign in</Link>
            </Button>
            <Button asChild>
              <Link to="/register">Get started</Link>
            </Button>
          </div>
        </div>
      </header>

      <main id="main" className="relative z-10">
        {/* hero */}
        <section className="mx-auto max-w-6xl px-4 pt-16 pb-12 text-center sm:px-6 sm:pt-24">
          <div className="animate-in fade-in slide-in-from-bottom-3 duration-700 motion-reduce:animate-none">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
              <span className="size-1.5 rounded-full bg-emerald-400" aria-hidden />
              Private by design · Your data stays yours
            </span>
            <h1 className="mx-auto mt-6 max-w-4xl text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">
              Run your job search like a{" "}
              <span className="bg-gradient-to-r from-primary via-violet-400 to-sky-400 bg-clip-text text-transparent">
                command center
              </span>
              .
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-pretty text-muted-foreground">
              Track every opportunity, recruiter and follow-up in one place. See exactly what to do
              today, and learn what is working week by week.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button asChild size="lg" className="h-11 px-6 text-base shadow-lg shadow-primary/30">
                <Link to="/register">
                  Create your account
                  <ArrowRight data-icon="inline-end" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-11 px-6 text-base">
                <Link to="/login">I already have an account</Link>
              </Button>
            </div>
          </div>

          <div className="relative mx-auto mt-16 max-w-5xl animate-in fade-in slide-in-from-bottom-6 text-left delay-150 duration-1000 motion-reduce:animate-none">
            <div
              aria-hidden
              className="absolute -inset-x-6 -bottom-10 h-40 bg-gradient-to-t from-background to-transparent"
            />
            <ProductPreview />
          </div>
        </section>

        {/* facts */}
        <section aria-label="At a glance" className="border-y border-border/60 bg-card/30">
          <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-px px-4 py-10 sm:px-6 lg:grid-cols-4">
            {FACTS.map((f) => (
              <div key={f.value} className="px-4 py-2 text-center">
                <dt className="font-mono text-3xl font-semibold tracking-tight text-primary sm:text-4xl">
                  {f.value}
                </dt>
                <dd className="mx-auto mt-2 max-w-[14rem] text-sm text-muted-foreground">
                  {f.label}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* features */}
        <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
          <SectionHeading
            eyebrow="Features"
            title="Everything a serious search needs, nothing it does not"
            body="Built around the real rhythm of job hunting: apply, follow up, interview, repeat."
          />
          <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <article
                key={f.title}
                className={cn(
                  "group relative overflow-hidden rounded-2xl border border-border/80 bg-card/60 p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-xl hover:shadow-primary/10 motion-reduce:transition-none motion-reduce:hover:translate-y-0",
                  f.className,
                )}
              >
                <div
                  aria-hidden
                  className="absolute -top-16 -right-16 size-40 rounded-full bg-primary/10 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
                />
                <span className="flex size-10 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/25">
                  <f.icon className="size-5" aria-hidden />
                </span>
                <h3 className="mt-5 text-lg font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        {/* how it works */}
        <section
          id="how-it-works"
          className="scroll-mt-20 border-y border-border/60 bg-card/30 py-24"
        >
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <SectionHeading eyebrow="How it works" title="From first lead to signed offer" />
            <ol className="mt-14 grid gap-6 md:grid-cols-3">
              {STEPS.map((s, i) => (
                <li
                  key={s.title}
                  className="relative rounded-2xl border border-border/80 bg-background/60 p-6"
                >
                  <span className="flex size-9 items-center justify-center rounded-full bg-primary font-mono text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/30">
                    {i + 1}
                  </span>
                  <h3 className="mt-5 text-lg font-semibold tracking-tight">{s.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* privacy */}
        <section id="privacy" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
          <SectionHeading
            eyebrow="Privacy and security"
            title="A personal tool should stay personal"
            body="Job searches are sensitive. The app is built so your pipeline is visible only to you."
          />
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PRIVACY_POINTS.map((p) => (
              <div key={p.title} className="rounded-2xl border border-border/80 bg-card/60 p-5">
                <p.icon className="size-5 text-primary" aria-hidden />
                <h3 className="mt-4 font-semibold tracking-tight">{p.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{p.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* final CTA */}
        <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
          <div className="relative overflow-hidden rounded-3xl border border-primary/30 bg-gradient-to-br from-primary/20 via-card to-violet-500/10 px-6 py-16 text-center sm:px-12">
            <div
              aria-hidden
              className="absolute -top-24 left-1/2 size-80 -translate-x-1/2 rounded-full bg-primary/30 blur-[100px]"
            />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
                Make your next application count
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
                Set up in a minute. Bring your current list, or start fresh with the quick-add
                shortcut.
              </p>
              <ul className="mx-auto mt-6 flex max-w-md flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
                {[
                  "Private to your account",
                  "Google or email sign-in",
                  "Light and dark themes",
                ].map((t) => (
                  <li key={t} className="flex items-center gap-1.5">
                    <Check className="size-4 text-emerald-400" aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
              <Button
                asChild
                size="lg"
                className="mt-8 h-11 px-6 text-base shadow-lg shadow-primary/30"
              >
                <Link to="/register">
                  Get started
                  <ArrowRight data-icon="inline-end" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-border/60 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:px-6">
          <Logo />
          <nav
            aria-label="Footer"
            className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2"
          >
            <Link to="/login" className="hover:text-foreground">
              Sign in
            </Link>
            <Link to="/register" className="hover:text-foreground">
              Create account
            </Link>
            {TERMS_URL ? (
              <a
                href={TERMS_URL}
                className="hover:text-foreground"
                rel="noreferrer"
                target="_blank"
              >
                Terms
              </a>
            ) : null}
            {PRIVACY_URL ? (
              <a
                href={PRIVACY_URL}
                className="hover:text-foreground"
                rel="noreferrer"
                target="_blank"
              >
                Privacy policy
              </a>
            ) : null}
          </nav>
          <p>© {COPYRIGHT_YEAR} Jobs Tracker</p>
        </div>
      </footer>
    </div>
  )
}

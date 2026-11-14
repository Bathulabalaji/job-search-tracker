import { ArrowLeft, BriefcaseBusiness, GitBranch, Mail, Phone, type LucideIcon } from "lucide-react"
import { Link } from "react-router-dom"

import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Logo } from "@/components/common/logo"
import { CONTACT } from "@/lib/env"

export interface ContactDetails {
  name: string
  email: string
  phone: string
  linkedinUrl: string
  githubUrl: string
}

/** Only http(s) links are shown, so a typo in an env var can never become a script link. */
function webLink(value: string): string | null {
  try {
    const url = new URL(value.trim())
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null
  } catch {
    return null
  }
}

const hostPath = (href: string): string =>
  href.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")

interface Entry {
  icon: LucideIcon
  label: string
  value: string
  href: string
  external?: boolean
}

function entriesFor(details: ContactDetails): Entry[] {
  const entries: Entry[] = []
  const email = details.email.trim()
  if (/^\S+@\S+\.\S+$/.test(email)) {
    entries.push({
      icon: Mail,
      label: "Email",
      value: email,
      href: `mailto:${email}?subject=${encodeURIComponent("Career Command Center")}`,
    })
  }
  const phone = details.phone.trim()
  const dial = phone.replace(/[^\d+]/g, "")
  if (dial.replace(/\D/g, "").length >= 6) {
    entries.push({ icon: Phone, label: "Phone", value: phone, href: `tel:${dial}` })
  }
  const linkedin = webLink(details.linkedinUrl)
  if (linkedin) {
    entries.push({
      icon: BriefcaseBusiness,
      label: "LinkedIn",
      value: hostPath(linkedin),
      href: linkedin,
      external: true,
    })
  }
  const github = webLink(details.githubUrl)
  if (github) {
    entries.push({
      icon: GitBranch,
      label: "GitHub",
      value: hostPath(github),
      href: github,
      external: true,
    })
  }
  return entries
}

/** Public page, reachable signed in or out. */
export function ContactPage({ details = CONTACT }: { details?: ContactDetails }) {
  const entries = entriesFor(details)
  const name = details.name.trim()
  return (
    <div className="relative min-h-dvh overflow-x-clip bg-background text-foreground">
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-80">
        <div className="absolute top-[-10rem] left-1/2 size-[36rem] -translate-x-1/2 rounded-full bg-primary/20 blur-[110px]" />
      </div>

      <header className="relative border-b border-border/60 pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-4 px-4 sm:px-6">
          <Logo />
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-2xl px-4 py-16 sm:px-6 sm:py-24">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 rounded text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          Back to home
        </Link>

        <h1 className="mt-6 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Contact
        </h1>
        <p className="mt-3 text-pretty text-muted-foreground">
          {name ? `Hi, I'm ${name}. ` : ""}Questions, feedback or a problem with Career Command
          Center? Send a message and include what you were doing when it happened.
        </p>

        {entries.length ? (
          <ul className="mt-10 grid gap-3 sm:grid-cols-2">
            {entries.map((entry) => (
              <li key={entry.label}>
                <a
                  href={entry.href}
                  {...(entry.external ? { target: "_blank", rel: "noreferrer noopener" } : {})}
                  className="group flex h-full items-center gap-4 rounded-2xl border border-border/80 bg-card/60 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/10 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/25">
                    <entry.icon className="size-5" aria-hidden />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs tracking-wide text-muted-foreground uppercase">
                      {entry.label}
                    </span>
                    <span className="block truncate font-medium">{entry.value}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-10 rounded-2xl border border-border/80 bg-card/60 p-6 text-sm text-muted-foreground">
            Contact details have not been set up yet.
          </p>
        )}
      </main>
    </div>
  )
}

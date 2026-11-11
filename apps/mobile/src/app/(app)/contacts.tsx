import { useState } from "react"
import { Linking, View } from "react-native"

import { useContactsList } from "@/api/contacts"
import { useResumes } from "@/api/resumes"
import { CONTACT_ROLES, type Contact, type ContactRole, type Resume } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Chip, ChipRow } from "@/components/ui/chip"
import { Screen } from "@/components/ui/screen"
import { SearchBar } from "@/components/ui/search-bar"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { SkeletonList } from "@/components/ui/skeleton"
import { EmptyState, ErrorState } from "@/components/ui/states"
import { Text } from "@/components/ui/text"
import { ContactSheet } from "@/features/contacts/contact-sheet"
import { ResumeSheet } from "@/features/resumes/resume-sheet"
import { titleCase } from "@/lib/format"
import { useDebouncedValue } from "@/lib/use-debounced-value"
import { space } from "@/theme/tokens"

type Tab = "contacts" | "resumes"
const TABS = [
  { value: "contacts", label: "Contacts" },
  { value: "resumes", label: "Resumes" },
] as const

export default function ContactsScreen() {
  const [tab, setTab] = useState<Tab>("contacts")
  return (
    <Screen edges={[]}>
      <SegmentedControl options={TABS} value={tab} onChange={setTab} />
      {tab === "contacts" ? <ContactsTab /> : <ResumesTab />}
    </Screen>
  )
}

function ContactsTab() {
  const [search, setSearch] = useState("")
  const [role, setRole] = useState<ContactRole | undefined>()
  const q = useDebouncedValue(search.trim(), 300)
  const { data, isPending, isError, error, refetch } = useContactsList({ q: q || undefined, role })
  const [sheet, setSheet] = useState<{ open: boolean; contact: Contact | null }>({ open: false, contact: null })

  return (
    <View style={{ gap: space.md }}>
      <SearchBar value={search} onChangeText={setSearch} placeholder="Search contacts" />
      <View style={{ marginHorizontal: -space.lg }}>
        <ChipRow>
          <Chip label="All" selected={role === undefined} onPress={() => setRole(undefined)} />
          {CONTACT_ROLES.map((r) => (
            <Chip key={r} label={titleCase(r)} selected={role === r} onPress={() => setRole(role === r ? undefined : r)} />
          ))}
        </ChipRow>
      </View>
      <Button label="Add contact" icon="person-add-outline" onPress={() => setSheet({ open: true, contact: null })} />
      {isPending ? <SkeletonList count={3} /> : null}
      {isError ? <ErrorState error={error} onRetry={() => void refetch()} /> : null}
      {data && !data.length ? (
        <EmptyState icon="people-outline" title={q || role ? "No matches" : "No contacts yet"} description="Recruiters, managers and referrers you talk to will live here." />
      ) : null}
      {data?.map((c) => (
        <Card key={c.id} onPress={() => setSheet({ open: true, contact: c })}>
          <Text style={{ fontWeight: "600" }}>{c.name}</Text>
          <Text variant="small" tone="muted">
            {titleCase(c.role)}
            {c.company ? ` · ${c.company}` : ""}
          </Text>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
            {c.phone ? <Button label="Call" icon="call" size="sm" variant="secondary" fullWidth={false} onPress={() => void Linking.openURL(`tel:${c.phone}`)} /> : null}
            {c.email ? <Button label="Email" icon="mail" size="sm" variant="secondary" fullWidth={false} onPress={() => void Linking.openURL(`mailto:${c.email}`)} /> : null}
            {c.linkedin_url ? <Button label="LinkedIn" icon="logo-linkedin" size="sm" variant="secondary" fullWidth={false} onPress={() => void Linking.openURL(c.linkedin_url ?? "")} /> : null}
          </View>
        </Card>
      ))}
      <ContactSheet visible={sheet.open} contact={sheet.contact} onClose={() => setSheet({ open: false, contact: null })} />
    </View>
  )
}

function ResumesTab() {
  const [search, setSearch] = useState("")
  const q = useDebouncedValue(search.trim(), 300)
  const { data, isPending, isError, error, refetch } = useResumes(q)
  const [sheet, setSheet] = useState<{ open: boolean; resume: Resume | null }>({ open: false, resume: null })

  return (
    <View style={{ gap: space.md }}>
      <SearchBar value={search} onChangeText={setSearch} placeholder="Search resumes" />
      <Button label="Add resume" icon="add" onPress={() => setSheet({ open: true, resume: null })} />
      {isPending ? <SkeletonList count={3} /> : null}
      {isError ? <ErrorState error={error} onRetry={() => void refetch()} /> : null}
      {data && !data.length ? (
        <EmptyState icon="document-text-outline" title={q ? "No matches" : "No resumes yet"} description="Track which version you sent where. Only names and notes are stored, not files." />
      ) : null}
      {data?.map((r) => (
        <Card key={r.id} onPress={() => setSheet({ open: true, resume: r })}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Text style={{ fontWeight: "600", flex: 1 }}>{r.label}</Text>
            <Badge label={`v${r.version}`} tone="primary" />
          </View>
          {r.focus ? <Text variant="small" tone="muted">{r.focus}</Text> : null}
          {r.file_name ? <Text variant="caption" tone="muted">{r.file_name}</Text> : null}
        </Card>
      ))}
      <ResumeSheet visible={sheet.open} resume={sheet.resume} onClose={() => setSheet({ open: false, resume: null })} />
    </View>
  )
}

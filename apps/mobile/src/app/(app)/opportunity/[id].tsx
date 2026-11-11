import { Stack, useLocalSearchParams, useRouter } from "expo-router"
import { useState } from "react"
import { Alert, Linking, View } from "react-native"

import { useContacts, useDeleteContact } from "@/api/contacts"
import { useUpdateFollowup, useFollowups } from "@/api/followups"
import { useInteractions } from "@/api/interactions"
import {
  useDeleteOpportunity,
  useMoveOpportunity,
  useOpportunity,
} from "@/api/opportunities"
import type { Contact, Followup, Interaction, InteractionType } from "@/api/types"
import { PriorityBadge, StageBadge } from "@/components/opportunity/badges"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Icon, type IconName } from "@/components/ui/icon"
import { IconButton } from "@/components/ui/icon-button"
import { OptionSheet } from "@/components/ui/option-sheet"
import { Screen, SectionHeader } from "@/components/ui/screen"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { SkeletonList } from "@/components/ui/skeleton"
import { EmptyState, ErrorState } from "@/components/ui/states"
import { Text } from "@/components/ui/text"
import { ContactSheet } from "@/features/contacts/contact-sheet"
import { FollowupSheet } from "@/features/detail/followup-sheet"
import { LogInteractionSheet } from "@/features/detail/log-interaction-sheet"
import { STAGE_OPTIONS } from "@/features/pipeline/options"
import { formatDate, formatDateTime, titleCase } from "@/lib/format"
import { haptics } from "@/lib/haptics"
import { toast } from "@/lib/toast-bus"

type Tab = "overview" | "timeline" | "followups" | "contacts"
const TABS = [
  { value: "overview", label: "Overview" },
  { value: "timeline", label: "Timeline" },
  { value: "followups", label: "Follow-ups" },
  { value: "contacts", label: "Contacts" },
] as const

const INTERACTION_ICONS: Record<InteractionType, IconName> = {
  call: "call-outline",
  email: "mail-outline",
  linkedin: "logo-linkedin",
  whatsapp: "logo-whatsapp",
  interview: "people-outline",
  nudge: "notifications-outline",
  stage_change: "swap-horizontal",
}

export default function OpportunityDetailScreen() {
  const router = useRouter()
  const { id: idParam } = useLocalSearchParams<{ id: string }>()
  const id = Number(idParam)
  const opportunity = useOpportunity(id)
  const move = useMoveOpportunity()
  const remove = useDeleteOpportunity()

  const [tab, setTab] = useState<Tab>("overview")
  const [menu, setMenu] = useState(false)
  const [moving, setMoving] = useState(false)
  const [logging, setLogging] = useState(false)
  const [addingFollowup, setAddingFollowup] = useState(false)
  const [contactSheet, setContactSheet] = useState<{ open: boolean; contact: Contact | null }>({
    open: false,
    contact: null,
  })

  if (opportunity.isPending) {
    return (
      <Screen edges={[]}>
        <SkeletonList count={3} />
      </Screen>
    )
  }
  if (opportunity.isError) {
    return (
      <Screen edges={[]}>
        <ErrorState
          title={opportunity.error.message.includes("not found") ? "Opportunity not found" : undefined}
          error={opportunity.error}
          onRetry={() => void opportunity.refetch()}
        />
      </Screen>
    )
  }

  const o = opportunity.data

  const confirmDelete = () =>
    Alert.alert(
      `Delete ${o.company}?`,
      "This also deletes its timeline and follow-ups. This can't be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () =>
            remove.mutate(o.id, {
              onSuccess: () => {
                haptics.success()
                toast.success(`Deleted ${o.company}`)
                router.back()
              },
              onError: (e) => toast.error("Could not delete", e.message),
            }),
        },
      ],
    )

  return (
    <Screen
      edges={[]}
      refreshing={opportunity.isRefetching}
      onRefresh={() => void opportunity.refetch()}
    >
      <Stack.Screen
        options={{
          title: "",
          headerRight: () => (
            <IconButton icon="ellipsis-horizontal" label="More actions" onPress={() => setMenu(true)} />
          ),
        }}
      />

      <View style={{ gap: 6 }}>
        <Text variant="title" accessibilityRole="header">
          {o.company}
        </Text>
        <Text tone="muted" variant="body">
          {o.role}
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
          <StageBadge stage={o.stage} />
          <PriorityBadge priority={o.priority} />
          {o.fit_score !== null ? <Badge label={`${o.fit_score}% fit`} tone="success" /> : null}
          {o.ghosted_suggestion ? <Badge label="Maybe ghosted" tone="warning" /> : null}
        </View>
      </View>

      <View style={{ flexDirection: "row", gap: 8 }}>
        <Button label="Move stage" icon="swap-horizontal" variant="secondary" size="sm" style={{ flex: 1 }} onPress={() => setMoving(true)} />
        <Button label="Log" icon="chatbubble-outline" size="sm" style={{ flex: 1 }} onPress={() => setLogging(true)} />
      </View>

      <SegmentedControl options={TABS} value={tab} onChange={setTab} />

      {tab === "overview" ? <Overview o={o} /> : null}
      {tab === "timeline" ? <Timeline id={id} onLog={() => setLogging(true)} /> : null}
      {tab === "followups" ? <Followups id={id} onAdd={() => setAddingFollowup(true)} /> : null}
      {tab === "contacts" ? (
        <Contacts
          id={id}
          onAdd={() => setContactSheet({ open: true, contact: null })}
          onEdit={(contact) => setContactSheet({ open: true, contact })}
        />
      ) : null}

      <OptionSheet
        visible={menu}
        title={o.company}
        options={[
          { value: "edit", label: "Edit details", icon: "create-outline" },
          { value: "delete", label: "Delete opportunity", icon: "trash-outline" },
        ]}
        onSelect={(action) => {
          if (action === "edit") router.push({ pathname: "/opportunity/form", params: { id: o.id } })
          else confirmDelete()
        }}
        onClose={() => setMenu(false)}
      />
      <OptionSheet
        visible={moving}
        title="Move to…"
        options={STAGE_OPTIONS}
        value={o.stage}
        onSelect={(stage) => {
          if (stage !== o.stage) {
            haptics.success()
            move.mutate({ id: o.id, stage })
          }
        }}
        onClose={() => setMoving(false)}
      />
      <LogInteractionSheet visible={logging} onClose={() => setLogging(false)} opportunityId={o.id} />
      <FollowupSheet visible={addingFollowup} onClose={() => setAddingFollowup(false)} opportunityId={o.id} />
      <ContactSheet
        visible={contactSheet.open}
        contact={contactSheet.contact}
        opportunityId={o.id}
        defaultCompany={o.company}
        onClose={() => setContactSheet({ open: false, contact: null })}
      />
    </Screen>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <View style={{ gap: 2 }}>
      <Text variant="caption" tone="muted">
        {label}
      </Text>
      <Text>{value}</Text>
    </View>
  )
}

function Overview({ o }: { o: NonNullable<ReturnType<typeof useOpportunity>["data"]> }) {
  return (
    <View style={{ gap: 12 }}>
      <Card style={{ gap: 14 }}>
        <Row label="Source" value={titleCase(o.source)} />
        <Row label="Location" value={[o.location, o.work_mode ? titleCase(o.work_mode) : null].filter(Boolean).join(" · ")} />
        <Row label="Compensation note" value={o.expected_ctc_note} />
        <Row
          label="Last contact"
          value={o.last_contact_at ? `${formatDateTime(o.last_contact_at)} (${o.days_since_contact}d ago)` : "No contact yet"}
        />
        {o.stack_tags.length ? (
          <View style={{ gap: 6 }}>
            <Text variant="caption" tone="muted">
              Stack
            </Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
              {o.stack_tags.map((t) => (
                <Badge key={t} label={t} tone="primary" />
              ))}
            </View>
          </View>
        ) : null}
      </Card>

      {o.next_action ? (
        <Card style={{ borderColor: "transparent" }}>
          <Text variant="caption" tone="muted">
            Next action
          </Text>
          <Text style={{ fontWeight: "600" }}>{o.next_action}</Text>
          {o.next_action_due ? (
            <Text variant="small" tone="muted">
              Due {formatDate(o.next_action_due)}
            </Text>
          ) : null}
        </Card>
      ) : null}

      {o.jd_url ? (
        <Button
          label="Open job posting"
          icon="open-outline"
          variant="secondary"
          onPress={() => void Linking.openURL(o.jd_url ?? "")}
        />
      ) : null}
      {o.jd_text ? (
        <Card>
          <Text variant="caption" tone="muted">
            Job description / notes
          </Text>
          <Text variant="small" selectable>
            {o.jd_text}
          </Text>
        </Card>
      ) : null}
    </View>
  )
}

function Timeline({ id, onLog }: { id: number; onLog: () => void }) {
  const { data, isPending, isError, error, refetch } = useInteractions(id)
  if (isPending) return <SkeletonList count={3} />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  const sorted: Interaction[] = [...data].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at))
  if (!sorted.length)
    return (
      <EmptyState
        icon="time-outline"
        title="No activity yet"
        description="Log calls, emails and messages to build a timeline."
        actionLabel="Log activity"
        onAction={onLog}
      />
    )
  return (
    <View style={{ gap: 10 }}>
      {sorted.map((i) => (
        <Card key={i.id}>
          <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}>
            <Icon name={INTERACTION_ICONS[i.type]} color="primary" />
            <Text style={{ fontWeight: "600", flex: 1 }}>
              {titleCase(i.type)}
              {i.type !== "stage_change" ? (i.direction === "in" ? " · incoming" : " · outgoing") : ""}
            </Text>
            <Text variant="caption" tone="muted">
              {formatDateTime(i.occurred_at)}
            </Text>
          </View>
          {i.summary ? <Text variant="small">{i.summary}</Text> : null}
        </Card>
      ))}
    </View>
  )
}

function FollowupRow({ f, opportunityId }: { f: Followup; opportunityId: number }) {
  const update = useUpdateFollowup()
  const pending = f.status === "pending"
  return (
    <Card>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
        <Icon name={pending ? "time-outline" : "checkmark-circle"} color={pending ? "warning" : "success"} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: "600" }}>
            {titleCase(f.channel)} · {formatDate(f.due_date)}
          </Text>
          {f.message_draft ? (
            <Text variant="small" tone="muted" numberOfLines={2}>
              {f.message_draft}
            </Text>
          ) : null}
        </View>
        <Badge label={titleCase(f.status)} tone={pending ? "warning" : f.status === "done" ? "success" : "neutral"} />
      </View>
      {pending ? (
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Button
            label="Done"
            icon="checkmark"
            size="sm"
            style={{ flex: 1 }}
            onPress={() =>
              update.mutate({ id: f.id, opportunityId, patch: { status: "done" }, message: "Marked done" })
            }
          />
          <Button
            label="Skip"
            size="sm"
            variant="secondary"
            style={{ flex: 1 }}
            onPress={() =>
              update.mutate({ id: f.id, opportunityId, patch: { status: "skipped" }, message: "Skipped" })
            }
          />
        </View>
      ) : null}
    </Card>
  )
}

function Followups({ id, onAdd }: { id: number; onAdd: () => void }) {
  const { data, isPending, isError, error, refetch } = useFollowups(id)
  if (isPending) return <SkeletonList count={2} />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  const sorted = [...data].sort((a, b) =>
    a.status === b.status ? a.due_date.localeCompare(b.due_date) : a.status === "pending" ? -1 : 1,
  )
  return (
    <View style={{ gap: 10 }}>
      <SectionHeader
        title="Follow-ups"
        right={<Button label="Add" icon="add" size="sm" fullWidth={false} onPress={onAdd} />}
      />
      {sorted.length ? (
        sorted.map((f) => <FollowupRow key={f.id} f={f} opportunityId={id} />)
      ) : (
        <EmptyState
          icon="alarm-outline"
          title="No follow-ups"
          description="One is created automatically when you move to Applied or Screening."
        />
      )}
    </View>
  )
}

function Contacts({
  id,
  onAdd,
  onEdit,
}: {
  id: number
  onAdd: () => void
  onEdit: (contact: Contact) => void
}) {
  const { data, isPending, isError, error, refetch } = useContacts(id)
  const remove = useDeleteContact()
  if (isPending) return <SkeletonList count={2} />
  if (isError) return <ErrorState error={error} onRetry={() => void refetch()} />
  return (
    <View style={{ gap: 10 }}>
      <SectionHeader
        title="Contacts"
        right={<Button label="Add" icon="add" size="sm" fullWidth={false} onPress={onAdd} />}
      />
      {data.length ? (
        data.map((c) => (
          <Card
            key={c.id}
            onPress={() => onEdit(c)}
            onLongPress={() =>
              Alert.alert(`Delete ${c.name}?`, undefined, [
                { text: "Cancel", style: "cancel" },
                { text: "Delete", style: "destructive", onPress: () => remove.mutate(c.id) },
              ])
            }
          >
            <Text style={{ fontWeight: "600" }}>{c.name}</Text>
            <Text variant="small" tone="muted">
              {titleCase(c.role)}
              {c.company ? ` · ${c.company}` : ""}
            </Text>
            <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
              {c.phone ? (
                <Button label="Call" icon="call" size="sm" variant="secondary" fullWidth={false} onPress={() => void Linking.openURL(`tel:${c.phone}`)} />
              ) : null}
              {c.email ? (
                <Button label="Email" icon="mail" size="sm" variant="secondary" fullWidth={false} onPress={() => void Linking.openURL(`mailto:${c.email}`)} />
              ) : null}
            </View>
          </Card>
        ))
      ) : (
        <EmptyState icon="person-add-outline" title="No contacts yet" description="Add the recruiter or hiring manager." />
      )}
    </View>
  )
}

import * as Clipboard from "expo-clipboard";
import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";

import { ApiError } from "@/api/client";
import {
  useMarkSent,
  usePolish,
  usePreview,
  useSuggestions,
  useTemplates,
  type OutreachChannel,
  type PolishInstruction,
} from "@/api/messaging";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Chip, ChipRow } from "@/components/ui/chip";
import { OptionSheet, type Option } from "@/components/ui/option-sheet";
import { Sheet } from "@/components/ui/sheet";
import { SkeletonList } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { TextField } from "@/components/ui/text-field";
import { formatDate } from "@/lib/format";
import { toast } from "@/lib/toast-bus";
import { useTheme } from "@/theme/theme";
import {
  fillGap,
  gapsIn,
  gmailLink,
  launch,
  linkedinTarget,
  mailtoLink,
  tooLongForMailto,
} from "./outreach-links";

const CHANNEL_LABELS: Record<OutreachChannel, string> = {
  email: "Email",
  linkedin: "LinkedIn",
  linkedin_note: "Connection note",
};

const POLISH: Option<PolishInstruction>[] = [
  { value: "shorter", label: "Make it shorter" },
  { value: "warmer", label: "Warmer tone" },
  { value: "more_formal", label: "More formal" },
  { value: "more_direct", label: "More direct" },
  { value: "fix_grammar", label: "Fix grammar only" },
];

/** The few fields the sheet needs, so a reminder or chat card can open it. */
export type OpportunityRef = { id: number; company: string; role: string };

export interface MessageSheetProps {
  opportunity: OpportunityRef;
  visible: boolean;
  onClose: () => void;
  initial?: {
    templateKey?: string;
    channel?: OutreachChannel;
    contactId?: number | null;
  };
}

export function MessageSheet({
  opportunity,
  visible,
  onClose,
  initial,
}: MessageSheetProps) {
  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      title={`Message for ${opportunity.company}`}
    >
      {/* Mounted only while open, so every opening starts fresh. */}
      {visible ? (
        <Composer
          opportunity={opportunity}
          initial={initial}
          onDone={onClose}
        />
      ) : null}
    </Sheet>
  );
}

interface Draft {
  key: string;
  subject: string | null;
  body: string;
}

function Composer({
  opportunity,
  initial,
  onDone,
}: {
  opportunity: OpportunityRef;
  initial: MessageSheetProps["initial"];
  onDone: () => void;
}) {
  const { colors } = useTheme();
  const suggestions = useSuggestions(opportunity.id);
  const templates = useTemplates();
  const [templateState, setTemplate] = useState<string | null>(
    initial?.templateKey ?? null,
  );
  const [channelState, setChannel] = useState<OutreachChannel | null>(
    initial?.channel ?? null,
  );
  const [contactState, setContact] = useState<number | null | undefined>(
    initial?.contactId === undefined ? undefined : initial.contactId,
  );
  const [draft, setDraft] = useState<Draft | null>(null);
  const [undo, setUndo] = useState<{
    subject: string | null;
    body: string;
  } | null>(null);
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const [pickingTemplate, setPickingTemplate] = useState(false);
  const [pickingContact, setPickingContact] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [gapValues, setGapValues] = useState<Record<string, string>>({});
  const [requestId] = useState(() =>
    `${Date.now()}-${Math.random()}`.replace(/\D/g, ""),
  );

  const advice = suggestions.data;
  const all = (templates.data ?? []).filter((t) => !t.archived);
  const firstDue = advice?.suggestions.find((s) => s.kind === "send" && s.due);
  const firstAny = advice?.suggestions.find(
    (s) => s.kind === "send" || s.kind === "wait",
  );
  const fallback = firstDue ?? firstAny ?? null;
  const templateKey =
    templateState ?? fallback?.template_key ?? all[0]?.key ?? null;
  const template = all.find((t) => t.key === templateKey) ?? null;
  const channels = template?.variants.map((v) => v.channel) ?? [];
  const channel: OutreachChannel =
    channelState && channels.includes(channelState)
      ? channelState
      : fallback?.template_key === templateKey &&
          fallback.channel &&
          channels.includes(fallback.channel)
        ? fallback.channel
        : (channels[0] ?? "email");
  const suggestedContact =
    fallback?.template_key === templateKey
      ? (fallback.contact_id ?? null)
      : null;
  const contactId =
    contactState === undefined
      ? (suggestedContact ?? advice?.contacts[0]?.id ?? null)
      : contactState;
  const contact = advice?.contacts.find((c) => c.id === contactId) ?? null;

  const preview = usePreview(opportunity.id, templateKey, channel, contactId);
  const key = `${templateKey}|${channel}|${contactId}`;
  const live = preview.data && !preview.isPlaceholderData ? preview.data : null;
  const text: Draft | null =
    draft?.key === key
      ? draft
      : live
        ? { key, subject: live.subject, body: live.body }
        : null;
  const uniqueGaps = text
    ? [...new Set(gapsIn(`${text.subject ?? ""}\n${text.body}`))]
    : [];

  const polish = usePolish(opportunity.id);
  const markSent = useMarkSent(opportunity.id);

  const edit = (next: { subject?: string | null; body?: string }) => {
    if (!text) return;
    setDraft({
      key,
      subject: next.subject !== undefined ? next.subject : text.subject,
      body: next.body ?? text.body,
    });
    setNeedsConfirm(false);
  };

  const pick = (nextKey: string) => {
    setTemplate(nextKey);
    setChannel(null);
    setContact(undefined);
    setDraft(null);
    setUndo(null);
    setNeedsConfirm(false);
  };

  const fill = (label: string) => {
    const value = (gapValues[label] ?? "").trim();
    if (!value || !text) return;
    edit({
      subject: text.subject
        ? fillGap(text.subject, label, value)
        : text.subject,
      body: fillGap(text.body, label, value),
    });
  };

  const copyText = async (): Promise<boolean> => {
    if (!text) return false;
    try {
      await Clipboard.setStringAsync(
        text.subject ? `Subject: ${text.subject}\n\n${text.body}` : text.body,
      );
      return true;
    } catch {
      toast.error("Couldn't copy", "Select the text and copy it yourself.");
      return false;
    }
  };

  const asDraft = () => ({
    to: live?.to ?? null,
    subject: text?.subject ?? null,
    body: text?.body ?? "",
    from: live?.from_email ?? null,
  });

  const openEmail = async () => {
    if (!text) return;
    const tooLong = tooLongForMailto(asDraft());
    if (tooLong && (await copyText()))
      toast.info(
        "Too long for a mail link",
        "It was copied. Paste it into the email.",
      );
    const opened = await launch(
      mailtoLink(tooLong ? { ...asDraft(), body: "" } : asDraft()),
    );
    if (!opened && (await copyText()))
      toast.info("No mail app found", "The message was copied instead.");
  };

  const openGmail = async () => {
    await launch(gmailLink(asDraft()));
  };

  const openLinkedIn = async () => {
    const target = linkedinTarget(contact, opportunity.company);
    if (await copyText())
      toast.success(
        "Message copied",
        target.isSearch
          ? "Opening a LinkedIn search for them. Paste it once you're in their profile."
          : "Open their message box and paste it.",
      );
    await launch(target.url);
  };

  const runPolish = (instruction: PolishInstruction) => {
    if (!text) return;
    polish.mutate(
      { subject: text.subject, body: text.body, instruction },
      {
        onSuccess: (result) => {
          if (!result.changed) {
            toast.info("No change", result.notice ?? "Nothing to change.");
            return;
          }
          setUndo({ subject: text.subject, body: text.body });
          setDraft({ key, subject: result.subject, body: result.body });
        },
        onError: (e) =>
          toast.error(
            "Couldn't rewrite that",
            e instanceof ApiError ? e.message : "Try again in a moment.",
          ),
      },
    );
  };

  const sent = () => {
    if (!text || !live) return;
    if (uniqueGaps.length > 0 && !needsConfirm) {
      setNeedsConfirm(true);
      return;
    }
    markSent.mutate(
      {
        template_key: live.template_key,
        channel: channel === "email" ? "email" : "linkedin",
        contact_id: contactId,
        subject: text.subject,
        body: text.body,
        schedule_next: true,
        request_id: requestId,
      },
      {
        onSuccess: (result) => {
          toast.success(
            "Logged as sent",
            result.next_followup_due
              ? `Next follow-up on ${formatDate(result.next_followup_due)}.`
              : "Added to the timeline.",
          );
          onDone();
        },
        onError: (e) =>
          toast.error(
            "Couldn't record that",
            e instanceof ApiError ? e.message : "Try again.",
          ),
      },
    );
  };

  if (suggestions.isLoading || templates.isLoading)
    return <SkeletonList count={3} />;

  const stop = advice?.suggestions.find((s) => s.kind === "stop");
  const addContact = advice?.suggestions.find((s) => s.kind === "add_contact");
  const reasons = Object.fromEntries(
    (advice?.suggestions ?? []).flatMap((s) =>
      s.template_key ? [[s.template_key, s.reason] as const] : [],
    ),
  );
  const dueKeys = new Set(
    advice?.suggestions
      .filter((s) => s.kind === "send" && s.due)
      .map((s) => s.template_key),
  );

  return (
    <View style={{ gap: 12 }}>
      <Text variant="small" tone="muted">
        You send it yourself from your own mail app or LinkedIn. Nothing is sent
        from here.
      </Text>
      {stop ? <Text variant="small">{stop.reason}</Text> : null}
      {addContact ? (
        <Text variant="small" tone="muted">
          {addContact.reason}
        </Text>
      ) : null}

      <Button
        label={template ? template.name : "Choose a message"}
        icon="document-text-outline"
        variant="secondary"
        onPress={() => setPickingTemplate(true)}
      />
      {templateKey && reasons[templateKey] ? (
        <Text variant="caption" tone="muted">
          {dueKeys.has(templateKey) ? "Next: " : ""}
          {reasons[templateKey]}
        </Text>
      ) : null}

      <ChipRow>
        {channels.map((c) => (
          <Chip
            key={c}
            label={CHANNEL_LABELS[c]}
            selected={c === channel}
            onPress={() => {
              setChannel(c);
              setDraft(null);
              setNeedsConfirm(false);
            }}
          />
        ))}
      </ChipRow>

      {advice && advice.contacts.length > 0 ? (
        <Button
          label={contact ? `To: ${contact.name}` : "To: nobody yet"}
          icon="person-outline"
          variant="ghost"
          size="sm"
          fullWidth={false}
          onPress={() => setPickingContact(true)}
        />
      ) : null}

      {!text ? (
        <SkeletonList count={2} />
      ) : (
        <>
          <Text variant="caption" tone="muted">
            From {live?.from_email}
            {live?.to ? `  ·  To ${live.to}` : ""}
          </Text>
          {live?.edited ? <Badge label="Your version" tone="info" /> : null}
          {text.subject !== null ? (
            <TextField
              label="Subject"
              value={text.subject}
              maxLength={200}
              onChangeText={(subject) => edit({ subject })}
            />
          ) : null}
          <TextField
            label="Message"
            value={text.body}
            multiline
            maxLength={3000}
            onChangeText={(body) => edit({ body })}
          />
          <Text variant="caption" tone="muted">
            {text.body.length}
            {live?.char_limit ? `/${live.char_limit}` : ""} characters
          </Text>

          <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
            <Button
              label="Improve with AI"
              icon="sparkles-outline"
              variant="secondary"
              size="sm"
              fullWidth={false}
              loading={polish.isPending}
              onPress={() => setPolishing(true)}
            />
            {undo ? (
              <Button
                label="Undo rewrite"
                icon="arrow-undo-outline"
                variant="ghost"
                size="sm"
                fullWidth={false}
                onPress={() => {
                  setDraft({ key, ...undo });
                  setUndo(null);
                }}
              />
            ) : null}
          </View>

          {uniqueGaps.length > 0 ? (
            <View
              style={{
                gap: 8,
                borderWidth: 1,
                borderStyle: "dashed",
                borderColor: colors.border,
                borderRadius: 10,
                padding: 10,
              }}
            >
              <Text variant="caption" tone="muted">
                Fill in the gaps
              </Text>
              {uniqueGaps.map((gap) => (
                <View key={gap} style={{ gap: 6 }}>
                  <TextField
                    label={gap}
                    value={gapValues[gap] ?? ""}
                    maxLength={200}
                    onChangeText={(v) =>
                      setGapValues((g) => ({ ...g, [gap]: v }))
                    }
                  />
                  <Button
                    label="Insert"
                    size="sm"
                    variant="secondary"
                    fullWidth={false}
                    disabled={!(gapValues[gap] ?? "").trim()}
                    onPress={() => fill(gap)}
                  />
                </View>
              ))}
            </View>
          ) : null}

          {live?.warnings
            .filter((w) => !w.startsWith("Fill in"))
            .map((w) => (
              <Text key={w} variant="small" style={{ color: colors.warning }}>
                {w}
              </Text>
            ))}
          {live?.attach ? (
            <Text variant="small" tone="muted">
              Attach your {live.attach.label} resume as a PDF
              {live.attach.score !== null
                ? ` (${live.attach.score}/100 fit)`
                : ""}
              . Links can't attach files.
            </Text>
          ) : null}
          {live?.tips.map((tip) => (
            <Text key={tip} variant="caption" tone="muted">
              • {tip}
            </Text>
          ))}

          {channel === "email" ? (
            <>
              <Button
                label="Open in email"
                icon="mail-outline"
                onPress={() => void openEmail()}
              />
              <Button
                label="Open in Gmail"
                icon="open-outline"
                variant="secondary"
                onPress={() => void openGmail()}
              />
            </>
          ) : (
            <Button
              label="Copy and open LinkedIn"
              icon="logo-linkedin"
              onPress={() => void openLinkedIn()}
            />
          )}
          <Button
            label="Copy"
            icon="copy-outline"
            variant="secondary"
            onPress={() =>
              void copyText().then((ok) => ok && toast.success("Copied"))
            }
          />
          {needsConfirm ? (
            <Text variant="small" style={{ color: colors.danger }}>
              This still has gaps like [[{uniqueGaps[0]}]]. Fill them in, or
              confirm to record it as sent anyway.
            </Text>
          ) : null}
          <Button
            label={needsConfirm ? "Mark sent anyway" : "I sent it"}
            icon="checkmark"
            variant={needsConfirm ? "danger" : "primary"}
            loading={markSent.isPending}
            onPress={sent}
          />
        </>
      )}

      <OptionSheet
        visible={pickingTemplate}
        title="Choose a message"
        options={all.map((t) => ({
          value: t.key,
          label: t.name,
          ...(reasons[t.key]
            ? { description: reasons[t.key] }
            : { description: t.group_label }),
        }))}
        value={templateKey}
        onSelect={(k) => {
          pick(k);
          setPickingTemplate(false);
        }}
        onClose={() => setPickingTemplate(false)}
      />
      <OptionSheet
        visible={pickingContact}
        title="Send to"
        options={[
          { value: 0, label: "Nobody yet" },
          ...(advice?.contacts ?? []).map((c) => ({
            value: c.id,
            label: c.name,
            description:
              c.last_messaged_days !== null
                ? `Messaged ${c.last_messaged_days} day(s) ago`
                : c.role,
          })),
        ]}
        value={contactId ?? 0}
        onSelect={(id) => {
          setContact(id === 0 ? null : id);
          setDraft(null);
          setPickingContact(false);
        }}
        onClose={() => setPickingContact(false)}
      />
      <OptionSheet
        visible={polishing}
        title="Improve with AI"
        options={POLISH}
        onSelect={(instruction) => {
          setPolishing(false);
          runPolish(instruction);
        }}
        onClose={() => setPolishing(false)}
      />
    </View>
  );
}

/** Where a draft card or reminder can send the user to see the whole opportunity. */
export function openOpportunity(id: number) {
  router.push({ pathname: "/opportunity/[id]", params: { id } });
}

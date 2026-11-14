import { useState } from "react";
import { View } from "react-native";

import { ApiError } from "@/api/client";
import {
  useCreateTemplate,
  useUpdateTemplate,
  type MessageTemplate,
  type OutreachChannel,
  type TemplateVariant,
} from "@/api/messaging";
import { Button } from "@/components/ui/button";
import { Chip, ChipRow } from "@/components/ui/chip";
import { Sheet } from "@/components/ui/sheet";
import { Text } from "@/components/ui/text";
import { TextField } from "@/components/ui/text-field";
import { toast } from "@/lib/toast-bus";
import { useTheme } from "@/theme/theme";

/** Fields a template may use; the server rejects any other name. */
export const MESSAGE_FIELDS = [
  "recipient_first", "company", "role", "my_name", "my_first_name", "headline",
  "proof_point", "bridge", "skills", "applied_when", "signature", "notice_period",
  "current_ctc", "expected_ctc", "my_location", "talking_point", "new_update",
  "availability", "decision_date", "round_label",
] as const; // prettier-ignore

const CHANNELS: { value: OutreachChannel; label: string }[] = [
  { value: "email", label: "Email" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "linkedin_note", label: "Connection note" },
];

export type EditTarget =
  | { mode: "new" }
  | { mode: "edit-custom"; template: MessageTemplate; variant: TemplateVariant }
  | {
      mode: "edit-system";
      template: MessageTemplate;
      variant: TemplateVariant;
    };

export function TemplateEditorSheet({
  target,
  onClose,
}: {
  target: EditTarget | null;
  onClose: () => void;
}) {
  return (
    <Sheet
      visible={target !== null}
      onClose={onClose}
      title={
        target?.mode === "new"
          ? "New template"
          : target?.mode === "edit-system"
            ? `Your copy of “${target.template.name}”`
            : "Edit template"
      }
    >
      {target ? (
        <Editor
          key={target.mode + ("template" in target ? target.template.key : "")}
          target={target}
          onClose={onClose}
        />
      ) : null}
    </Sheet>
  );
}

function Editor({
  target,
  onClose,
}: {
  target: EditTarget;
  onClose: () => void;
}) {
  const { colors } = useTheme();
  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const variant = target.mode === "new" ? null : target.variant;
  const [name, setName] = useState(
    target.mode === "new" ? "" : target.template.name,
  );
  const [channel, setChannel] = useState<OutreachChannel>(
    variant?.channel ?? "email",
  );
  const [subject, setSubject] = useState(variant?.subject ?? "");
  const [body, setBody] = useState(variant?.body ?? "");
  const [error, setError] = useState<string | null>(null);
  const pending = create.isPending || update.isPending;

  const fail = (e: Error) =>
    setError(e instanceof ApiError ? e.message : "Could not save.");
  const done = () => {
    toast.success("Template saved");
    onClose();
  };

  const save = () => {
    setError(null);
    const subj = channel === "email" ? subject.trim() : null;
    if (target.mode !== "new" && variant?.template_id) {
      update.mutate(
        {
          id: variant.template_id,
          patch:
            target.mode === "edit-custom"
              ? { name: name.trim(), subject: subj, body }
              : { subject: subj, body },
        },
        { onSuccess: done, onError: fail },
      );
    } else {
      create.mutate(
        {
          name: name.trim(),
          channel,
          subject: subj,
          body,
          ...(target.mode === "edit-system"
            ? { base_key: target.template.key.replace("sys:", "") }
            : {}),
        },
        { onSuccess: done, onError: fail },
      );
    }
  };

  return (
    <View style={{ gap: 12 }}>
      <Text variant="small" tone="muted">
        Use fields like {"{{recipient_first}}"} to fill in details. A line
        wrapped in {"{{?proof_point}}"} … {"{{/}}"} is dropped when that field
        is empty.
      </Text>
      {target.mode !== "edit-system" ? (
        <TextField
          label="Name"
          value={name}
          maxLength={120}
          onChangeText={setName}
        />
      ) : null}
      {target.mode === "new" ? (
        <ChipRow>
          {CHANNELS.map((c) => (
            <Chip
              key={c.value}
              label={c.label}
              selected={c.value === channel}
              onPress={() => setChannel(c.value)}
            />
          ))}
        </ChipRow>
      ) : null}
      {channel === "email" ? (
        <TextField
          label="Subject"
          value={subject}
          maxLength={200}
          onChangeText={setSubject}
        />
      ) : null}
      <TextField
        label="Message"
        value={body}
        multiline
        maxLength={3000}
        onChangeText={setBody}
      />
      <Text variant="caption" tone="muted">
        Tap a field to add it:
      </Text>
      <ChipRow>
        {MESSAGE_FIELDS.map((field) => (
          <Chip
            key={field}
            label={field}
            onPress={() => setBody((b) => `${b}{{${field}}}`)}
          />
        ))}
      </ChipRow>
      {error ? (
        <Text variant="small" style={{ color: colors.danger }}>
          {error}
        </Text>
      ) : null}
      <Button
        label="Save"
        loading={pending}
        disabled={
          !body.trim() || (target.mode !== "edit-system" && !name.trim())
        }
        onPress={save}
      />
    </View>
  );
}

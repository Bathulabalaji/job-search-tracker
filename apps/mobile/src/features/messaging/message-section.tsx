import { useState } from "react";
import { View } from "react-native";

import {
  useMarkReplied,
  useSentMessages,
  useSuggestions,
} from "@/api/messaging";
import type { Opportunity } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Text } from "@/components/ui/text";
import { formatDate } from "@/lib/format";
import { toast } from "@/lib/toast-bus";
import { MessageSheet } from "./message-sheet";

/** "What should I send next?" plus the messages already sent, on the opportunity page. */
export function MessageSection({ opportunity }: { opportunity: Opportunity }) {
  const [open, setOpen] = useState(false);
  const suggestions = useSuggestions(opportunity.id);
  const sent = useSentMessages(opportunity.id);
  const replied = useMarkReplied(opportunity.id);

  const items = suggestions.data?.suggestions ?? [];
  const next = items.find((s) => s.kind === "send" && s.due);
  const stop = items.find((s) => s.kind === "stop");
  const upcoming = items.find((s) => s.kind === "wait");
  const addContact = items.find((s) => s.kind === "add_contact");

  return (
    <Card style={{ gap: 10 }}>
      <Text style={{ fontWeight: "600" }}>Messages</Text>
      {next ? (
        <View style={{ gap: 2 }}>
          <Text variant="small" style={{ fontWeight: "600" }}>
            Next: {next.title}
          </Text>
          <Text variant="small" tone="muted">
            {next.reason}
          </Text>
        </View>
      ) : (
        <Text variant="small" tone="muted">
          {stop?.reason ??
            addContact?.reason ??
            (upcoming
              ? `Up next: ${upcoming.title}. ${upcoming.reason}`
              : "Nothing is due. You can still write a message any time.")}
        </Text>
      )}
      <Button
        label={next ? "Write it" : "Write a message"}
        icon={next ? "send" : "create-outline"}
        variant={next ? "primary" : "secondary"}
        onPress={() => setOpen(true)}
      />
      {(sent.data ?? []).slice(0, 4).map((m) => (
        <View
          key={m.id}
          style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
        >
          <View style={{ flex: 1 }}>
            <Text variant="small" numberOfLines={1}>
              {m.template_name ?? "Message"}
            </Text>
            <Text variant="caption" tone="muted">
              {m.channel === "email" ? "Email" : "LinkedIn"} ·{" "}
              {formatDate(m.sent_at)}
            </Text>
          </View>
          {m.replied_at ? (
            <Badge label="Replied" tone="success" />
          ) : (
            <Button
              label="They replied"
              size="sm"
              variant="ghost"
              fullWidth={false}
              loading={replied.isPending && replied.variables === m.id}
              onPress={() =>
                replied.mutate(m.id, {
                  onSuccess: () => toast.success("Logged their reply"),
                  onError: () => toast.error("Couldn't record that"),
                })
              }
            />
          )}
        </View>
      ))}
      <MessageSheet
        opportunity={opportunity}
        visible={open}
        onClose={() => setOpen(false)}
      />
    </Card>
  );
}

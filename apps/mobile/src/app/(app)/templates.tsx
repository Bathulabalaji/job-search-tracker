import { useState } from "react";
import { Alert, View } from "react-native";

import {
  useDeleteTemplate,
  useTemplates,
  type MessageTemplate,
  type TemplateVariant,
} from "@/api/messaging";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Screen, SectionHeader } from "@/components/ui/screen";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Text } from "@/components/ui/text";
import {
  TemplateEditorSheet,
  type EditTarget,
} from "@/features/messaging/template-editor-sheet";
import { toast } from "@/lib/toast-bus";

const CHANNEL_LABELS = {
  email: "Email",
  linkedin: "LinkedIn",
  linkedin_note: "Connection note",
} as const;

export default function TemplatesScreen() {
  const templates = useTemplates();
  const remove = useDeleteTemplate();
  const [editing, setEditing] = useState<EditTarget | null>(null);

  if (templates.isPending)
    return (
      <Screen edges={[]}>
        <SkeletonList count={4} />
      </Screen>
    );
  if (templates.isError)
    return (
      <Screen edges={[]}>
        <ErrorState
          error={templates.error}
          onRetry={() => void templates.refetch()}
        />
      </Screen>
    );

  const groups = new Map<string, MessageTemplate[]>();
  for (const t of templates.data)
    groups.set(t.group_label, [...(groups.get(t.group_label) ?? []), t]);

  const restore = (variant: TemplateVariant) => {
    if (variant.template_id === null) return;
    remove.mutate(variant.template_id, {
      onSuccess: () => toast.success("Restored the original"),
      onError: () => toast.error("Couldn't restore it"),
    });
  };

  const askDelete = (t: MessageTemplate, v: TemplateVariant) =>
    Alert.alert(`Delete “${t.name}”?`, undefined, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => restore(v) },
    ]);

  return (
    <Screen edges={[]}>
      <View style={{ gap: 12 }}>
        <Text variant="small" tone="muted">
          Ready-made messages for each stage. Edit one and your version is used
          from then on; you can restore the original any time.
        </Text>
        <Button
          label="New template"
          icon="add"
          onPress={() => setEditing({ mode: "new" })}
        />
        {[...groups.entries()].map(([label, items]) => (
          <View key={label} style={{ gap: 8 }}>
            <SectionHeader title={label} />
            {items.map((t) => (
              <Card key={t.key} style={{ gap: 6 }}>
                <Text style={{ fontWeight: "600" }}>
                  {t.name}
                  {t.india_only ? "  (India)" : ""}
                </Text>
                {t.summary ? (
                  <Text variant="small" tone="muted">
                    {t.summary}
                  </Text>
                ) : null}
                {t.variants.map((v) => (
                  <View
                    key={v.channel}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    <Text variant="small" style={{ flex: 1 }}>
                      {CHANNEL_LABELS[v.channel]}
                    </Text>
                    {v.edited ? (
                      <Badge label="Your version" tone="info" />
                    ) : null}
                    <Button
                      label="Edit"
                      size="sm"
                      variant="secondary"
                      fullWidth={false}
                      onPress={() =>
                        setEditing({
                          mode:
                            t.source === "custom"
                              ? "edit-custom"
                              : "edit-system",
                          template: t,
                          variant: v,
                        })
                      }
                    />
                    {t.source === "system" && v.edited ? (
                      <Button
                        label="Restore"
                        size="sm"
                        variant="ghost"
                        fullWidth={false}
                        onPress={() => restore(v)}
                      />
                    ) : null}
                    {t.source === "custom" ? (
                      <Button
                        label="Delete"
                        size="sm"
                        variant="danger"
                        fullWidth={false}
                        onPress={() => askDelete(t, v)}
                      />
                    ) : null}
                  </View>
                ))}
              </Card>
            ))}
          </View>
        ))}
      </View>
      <TemplateEditorSheet target={editing} onClose={() => setEditing(null)} />
    </Screen>
  );
}

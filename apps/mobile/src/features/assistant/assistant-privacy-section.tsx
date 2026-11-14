import { Platform, Switch, View } from "react-native";

import {
  useChatConfig,
  useQuotaUsage,
  useSetAssistantOptOut,
} from "@/api/chat";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress";
import { SectionHeader } from "@/components/ui/screen";
import { Text } from "@/components/ui/text";
import { toast } from "@/lib/toast-bus";
import { useTheme } from "@/theme/theme";

/** What the assistant sends where, today's allowances, and the switch that turns it all off. */
export function AssistantPrivacySection() {
  const { colors } = useTheme();
  const config = useChatConfig();
  const usage = useQuotaUsage();
  const setOptOut = useSetAssistantOptOut();
  // Hidden on servers without an assistant: nothing to explain or switch.
  if (!config.data || (!config.data.enabled && !config.data.assistant_opt_out))
    return null;
  const off = config.data.assistant_opt_out === true;

  const change = (assistantOn: boolean) =>
    setOptOut.mutate(!assistantOn, {
      onSuccess: () =>
        toast.success(
          assistantOn ? "AI assistant turned on" : "AI assistant turned off",
        ),
      onError: () => toast.error("Couldn't change that", "Try again."),
    });

  return (
    <View style={{ gap: 10 }}>
      <SectionHeader title="AI assistant" />
      <Card style={{ gap: 10 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }}>Use the AI assistant</Text>
            <Text variant="small" tone="muted">
              {off
                ? "Off: no chat, resume comparison, recommendations or resume indexing."
                : "Your questions and the redacted text of uploaded resumes are sent to the AI providers that answer them (Groq and Google). Job searches send only the search words."}
            </Text>
          </View>
          <Switch
            accessibilityLabel="Use the AI assistant"
            value={!off}
            disabled={setOptOut.isPending}
            onValueChange={change}
            trackColor={{ true: colors.primary, false: colors.border }}
            thumbColor={
              Platform.OS === "android" ? colors.onPrimary : undefined
            }
          />
        </View>
        {!off && usage.data && usage.data.length > 0 ? (
          <View style={{ gap: 8 }} accessibilityLabel="Today's allowances">
            {usage.data.map((q) => (
              <View key={q.name} style={{ gap: 4 }}>
                <View
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                  }}
                >
                  <Text variant="small">{q.label}</Text>
                  <Text variant="small" tone="muted">
                    {q.used}/{q.limit}
                  </Text>
                </View>
                <ProgressBar value={q.limit ? (q.used / q.limit) * 100 : 0} />
              </View>
            ))}
          </View>
        ) : null}
      </Card>
    </View>
  );
}

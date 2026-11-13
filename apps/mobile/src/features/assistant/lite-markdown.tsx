import { View } from "react-native";

import { Text } from "@/components/ui/text";

/**
 * Just enough markdown for assistant replies: paragraphs, "-"/"*"/"1." bullets and **bold**.
 * No dependency, no links and no HTML: model output is shown as text, never executed.
 */
function inline(text: string, keyPrefix: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <Text key={`${keyPrefix}-${index}`} style={{ fontWeight: "700" }}>
        {part.slice(2, -2)}
      </Text>
    ) : (
      part.replace(/`([^`]+)`/g, "$1")
    ),
  );
}

export function LiteMarkdown({ text }: { text: string }) {
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <View style={{ gap: 8 }}>
      {blocks.map((block, b) => {
        const lines = block.split("\n").filter((line) => line.trim() !== "");
        const bullets = lines.every((line) =>
          /^\s*([-*•]|\d+[.)])\s+/.test(line),
        );
        if (bullets) {
          return (
            <View key={b} style={{ gap: 4 }}>
              {lines.map((line, l) => {
                const numbered = line.trim().match(/^(\d+)[.)]\s+/);
                const body = line.replace(/^\s*([-*•]|\d+[.)])\s+/, "");
                return (
                  <View key={l} style={{ flexDirection: "row", gap: 8 }}>
                    <Text tone="muted">
                      {numbered ? `${numbered[1]}.` : "•"}
                    </Text>
                    <Text style={{ flex: 1 }}>{inline(body, `${b}-${l}`)}</Text>
                  </View>
                );
              })}
            </View>
          );
        }
        const heading = lines.length === 1 && /^#{1,6}\s+/.test(lines[0] ?? "");
        return (
          <Text key={b} style={heading ? { fontWeight: "700" } : undefined}>
            {inline(lines.join("\n").replace(/^#{1,6}\s+/, ""), String(b))}
          </Text>
        );
      })}
    </View>
  );
}

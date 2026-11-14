import { View } from "react-native";

import type { MatchResult, ResumeMatch } from "@/api/matching";
import { Badge } from "@/components/ui/badge";
import { ProgressBar } from "@/components/ui/progress";
import { Text } from "@/components/ui/text";
import { radius } from "@/theme/tokens";
import { useTheme } from "@/theme/theme";

function ResumeRow({ match, best }: { match: ResumeMatch; best: boolean }) {
  const { colors } = useTheme();
  return (
    <View
      accessibilityLabel={`${match.label}, fit ${match.score ?? "unknown"} out of 100`}
      style={{
        borderWidth: 1,
        borderColor: colors.border,
        borderRadius: radius.md,
        backgroundColor: colors.surface,
        padding: 12,
        gap: 8,
      }}
    >
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
        }}
      >
        <Text style={{ fontWeight: "600", flexShrink: 1 }} numberOfLines={1}>
          {match.label}
        </Text>
        {best ? <Badge label="Best fit" tone="success" /> : null}
        <Text variant="small">
          {match.score === null ? "—" : `${match.score}/100`}
        </Text>
      </View>
      <ProgressBar value={match.score ?? 0} />
      {match.vector_score !== null ? (
        <Text variant="caption" tone="muted">
          Text similarity {Math.round(match.vector_score * 100)}%
        </Text>
      ) : null}
      {match.matched_skills.length > 0 ? (
        <View style={{ gap: 4 }}>
          <Text variant="caption" tone="muted">
            Covers
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            {match.matched_skills.map((skill) => (
              <Badge key={skill} label={skill} tone="success" />
            ))}
          </View>
        </View>
      ) : null}
      {match.missing_skills.length > 0 ? (
        <View style={{ gap: 4 }}>
          <Text variant="caption" tone="muted">
            Missing
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            {match.missing_skills.map((skill) => (
              <Badge key={skill} label={skill} tone="warning" />
            ))}
          </View>
        </View>
      ) : null}
      {match.suggestions.map((suggestion) => (
        <Text key={suggestion} variant="small" tone="muted">
          • {suggestion}
        </Text>
      ))}
    </View>
  );
}

export function MatchBreakdown({ result }: { result: MatchResult }) {
  return (
    <View style={{ gap: 8 }} accessibilityLabel="Resume fit">
      {result.per_resume.map((match) => (
        <ResumeRow
          key={match.resume_id}
          match={match}
          best={
            result.per_resume.length > 1 &&
            match.resume_id === result.best_resume_id
          }
        />
      ))}
    </View>
  );
}

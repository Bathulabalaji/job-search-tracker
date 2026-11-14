import { View } from "react-native";

import { useChatConfig } from "@/api/chat";
import { ApiError } from "@/api/client";
import { useRunMatch, useStoredMatch } from "@/api/matching";
import { useUpdateOpportunity } from "@/api/opportunities";
import type { Opportunity } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Text } from "@/components/ui/text";
import { MatchBreakdown } from "@/features/matching/match-breakdown";
import { toast } from "@/lib/toast-bus";

/** "Which resume fits?": compares the uploaded resumes with this opportunity's JD. */
export function ResumeFitSection({
  opportunity,
}: {
  opportunity: Opportunity;
}) {
  const config = useChatConfig();
  const enabled = config.data?.matching === true;
  const stored = useStoredMatch(opportunity.id, enabled);
  const run = useRunMatch(opportunity.id);
  const update = useUpdateOpportunity(opportunity.id);
  if (!enabled) return null;

  const result = run.data ?? stored.data ?? null;
  const best = result?.per_resume.find(
    (m) => m.resume_id === result.best_resume_id,
  );
  const compare = (force: boolean) =>
    run.mutate(force, {
      onError: (e) =>
        toast.error(
          "Couldn't compare",
          e instanceof ApiError ? e.message : "Try again in a moment.",
        ),
    });
  const useScore = () => {
    if (best?.score == null) return;
    const score = best.score;
    update.mutate(
      { fit_score: score },
      { onSuccess: () => toast.success(`Fit score set to ${score}`) },
    );
  };

  return (
    <Card style={{ gap: 10 }}>
      <Text style={{ fontWeight: "600" }}>Which resume fits?</Text>
      {result ? (
        <>
          <MatchBreakdown result={result} />
          <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
            <Button
              label="Re-check"
              icon="refresh"
              variant="ghost"
              size="sm"
              fullWidth={false}
              loading={run.isPending}
              onPress={() => compare(true)}
            />
            {best?.score != null && best.score !== opportunity.fit_score ? (
              <Button
                label={`Use ${best.score} as fit score`}
                size="sm"
                fullWidth={false}
                loading={update.isPending}
                onPress={useScore}
              />
            ) : null}
          </View>
        </>
      ) : (
        <>
          <Text variant="small" tone="muted">
            Compare your uploaded resumes with this job description to see which
            fits best and what is missing.
          </Text>
          <Button
            label="Compare my resumes"
            icon="documents-outline"
            loading={run.isPending}
            onPress={() => compare(false)}
          />
        </>
      )}
    </Card>
  );
}

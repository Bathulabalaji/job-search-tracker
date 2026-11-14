import { useState } from "react";
import { View } from "react-native";

import { ApiError } from "@/api/client";
import {
  useDismissRecommendation,
  useRecommendations,
  useRefreshRecommendations,
  useSearchProfile,
} from "@/api/matching";
import { Button } from "@/components/ui/button";
import { Screen } from "@/components/ui/screen";
import { SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Text } from "@/components/ui/text";
import { JobCard } from "@/features/assistant/job-cards";
import { SearchProfileSheet } from "@/features/matching/search-profile-sheet";
import { toast } from "@/lib/toast-bus";

export default function RecommendationsScreen() {
  const feed = useRecommendations();
  const profile = useSearchProfile();
  const refresh = useRefreshRecommendations();
  const dismiss = useDismissRecommendation();
  const [editing, setEditing] = useState(false);

  const onRefresh = () =>
    refresh.mutate(undefined, {
      onSuccess: (result) => {
        if (result.added > 0)
          toast.success(
            `${result.added} new job${result.added === 1 ? "" : "s"}`,
          );
        else
          toast.info(
            result.notices[0]?.message ??
              "Nothing new that matches your resumes yet.",
          );
      },
      onError: (e) =>
        toast.error(
          "Couldn't refresh",
          e instanceof ApiError ? e.message : "Try again in a moment.",
        ),
    });

  return (
    <Screen
      edges={[]}
      refreshing={feed.isRefetching}
      onRefresh={() => void feed.refetch()}
    >
      <View style={{ gap: 12 }}>
        <Text variant="small" tone="muted">
          Fresh postings ranked by how closely they match your uploaded resumes.
        </Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Button
            label="Find new jobs"
            icon="refresh"
            size="sm"
            fullWidth={false}
            loading={refresh.isPending}
            onPress={onRefresh}
          />
          <Button
            label="Search profile"
            icon="options-outline"
            variant="secondary"
            size="sm"
            fullWidth={false}
            disabled={!profile.data}
            onPress={() => setEditing(true)}
          />
        </View>
        {feed.isPending ? (
          <SkeletonList count={3} />
        ) : feed.isError ? (
          <ErrorState error={feed.error} onRetry={() => void feed.refetch()} />
        ) : feed.data.length === 0 ? (
          <EmptyState
            icon="telescope-outline"
            title="No recommendations yet"
            description="Upload a resume PDF, then tap Find new jobs. It is limited to a couple of times a day."
          />
        ) : (
          feed.data.map((rec) => (
            <JobCard
              key={rec.id}
              job={rec.job}
              note={`${Math.round(rec.vector_score * 100)}% similar${
                rec.best_resume_label
                  ? ` · best resume: ${rec.best_resume_label}`
                  : ""
              }`}
              extraActions={
                <Button
                  label="Dismiss"
                  icon="close"
                  variant="ghost"
                  size="sm"
                  fullWidth={false}
                  onPress={() => dismiss.mutate(rec.id)}
                />
              }
            />
          ))
        )}
      </View>
      {profile.data ? (
        <SearchProfileSheet
          visible={editing}
          onClose={() => setEditing(false)}
          profile={profile.data}
        />
      ) : null}
    </Screen>
  );
}

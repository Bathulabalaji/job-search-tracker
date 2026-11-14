import * as WebBrowser from "expo-web-browser";
import { router } from "expo-router";
import { useState } from "react";
import { View } from "react-native";

import type { ChatAttachment, JobCardData, MatchCardData } from "@/api/chat";
import { ApiError } from "@/api/client";
import { useTrackJob } from "@/api/jobs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Text } from "@/components/ui/text";
import { MatchBreakdown } from "@/features/matching/match-breakdown";
import { haptics } from "@/lib/haptics";
import { toast } from "@/lib/toast-bus";
import { radius } from "@/theme/tokens";
import { useTheme } from "@/theme/theme";

const SITE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  naukri: "Naukri",
  indeed: "Indeed",
  company: "Company site",
  other: "Job board",
};

function postedLabel(postedAt: string | null): string | null {
  if (!postedAt) return null;
  const days = Math.floor(
    (Date.now() - new Date(postedAt).getTime()) / 86_400_000,
  );
  if (days <= 0) return "Posted today";
  if (days === 1) return "Posted yesterday";
  return `Posted ${days} days ago`;
}

/** Only http(s) links from the server's structured result are ever opened. */
function safeHref(url: string): string | null {
  return /^https?:\/\//i.test(url) ? url : null;
}

function activeBadge(status: string) {
  if (status === "active")
    return <Badge label="Verified open" tone="success" />;
  if (status === "inactive")
    return <Badge label="Looks closed" tone="danger" />;
  return <Badge label="Not verified" />;
}

export function JobCard({
  job,
  note,
  extraActions,
}: {
  job: JobCardData;
  /** A line under the badges, e.g. why this job was recommended. */
  note?: string;
  /** Buttons shown before Open and Track, e.g. Dismiss. */
  extraActions?: React.ReactNode;
}) {
  const { colors } = useTheme();
  const track = useTrackJob();
  const [trackedId, setTrackedId] = useState<number | null>(
    job.tracked_opportunity_id,
  );
  const href = safeHref(job.apply_url);
  const meta = [job.location, job.work_mode, job.salary_text]
    .filter(Boolean)
    .join(" · ");
  const posted = postedLabel(job.posted_at);

  const onTrack = () => {
    haptics.tap();
    track.mutate(job.id, {
      onSuccess: (opportunity) => {
        setTrackedId(opportunity.id);
        toast.success(`Added ${opportunity.company} to your pipeline`);
      },
      onError: (e) => {
        if (e instanceof ApiError && e.code === "already_tracked") {
          toast.info("This job is already in your pipeline.");
        } else {
          toast.error("Couldn't add the job", (e as Error).message);
        }
      },
    });
  };

  return (
    <View
      accessibilityLabel={`${job.title} at ${job.company}`}
      style={{
        borderWidth: 1,
        borderColor: colors.border,
        borderRadius: radius.md,
        backgroundColor: colors.surface,
        padding: 12,
        gap: 6,
      }}
    >
      <Text style={{ fontWeight: "600" }}>{job.title}</Text>
      <Text tone="muted" variant="small">
        {job.company}
        {meta ? ` · ${meta}` : ""}
      </Text>
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          gap: 6,
          alignItems: "center",
        }}
      >
        <Badge
          label={SITE_LABELS[job.source_site] ?? "Job board"}
          tone="info"
        />
        {activeBadge(job.active_status)}
        {posted ? (
          <Text tone="muted" variant="caption">
            {posted}
          </Text>
        ) : null}
      </View>
      {note ? (
        <Text tone="muted" variant="caption">
          {note}
        </Text>
      ) : null}
      <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
        {extraActions}
        {href ? (
          <Button
            label="Open"
            icon="open-outline"
            variant="secondary"
            size="sm"
            fullWidth={false}
            onPress={() => void WebBrowser.openBrowserAsync(href)}
          />
        ) : null}
        {trackedId !== null ? (
          <Button
            label="In pipeline"
            icon="checkmark-circle-outline"
            variant="ghost"
            size="sm"
            fullWidth={false}
            onPress={() =>
              router.push({
                pathname: "/opportunity/[id]",
                params: { id: trackedId },
              })
            }
          />
        ) : (
          <Button
            label="Track"
            icon="add"
            size="sm"
            fullWidth={false}
            loading={track.isPending}
            onPress={onTrack}
          />
        )}
      </View>
    </View>
  );
}

function MatchCard({ match }: { match: MatchCardData }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: colors.border,
        borderRadius: radius.md,
        backgroundColor: colors.surfaceRaised,
        padding: 12,
        gap: 8,
      }}
    >
      <Text style={{ fontWeight: "600" }}>
        Resume fit · {match.target_label}
      </Text>
      <MatchBreakdown result={match} />
      {match.target === "opportunity" ? (
        <Button
          label="Open opportunity"
          icon="open-outline"
          variant="secondary"
          size="sm"
          fullWidth={false}
          onPress={() =>
            router.push({
              pathname: "/opportunity/[id]",
              params: { id: match.target_id },
            })
          }
        />
      ) : null}
    </View>
  );
}

export function AttachmentList({ items }: { items: ChatAttachment[] }) {
  const jobs = items.filter((a): a is JobCardData => a.type === "job");
  const matches = items.filter((a): a is MatchCardData => a.type === "match");
  if (!jobs.length && !matches.length) return null;
  return (
    <View style={{ gap: 8, marginTop: 4 }} accessibilityLabel="Results">
      {matches.map((match) => (
        <MatchCard key={`${match.target}-${match.target_id}`} match={match} />
      ))}
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </View>
  );
}

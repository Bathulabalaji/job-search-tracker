import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Switch, View } from "react-native";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/client";
import {
  useOutreachProfile,
  useUpdateOutreachProfile,
  type OutreachProfile,
} from "@/api/messaging";
import { FormAlert } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { FormText } from "@/components/ui/form";
import { Sheet } from "@/components/ui/sheet";
import { Text } from "@/components/ui/text";
import { isOptionalWebUrl, normalizeWebUrl, WEB_URL_HINT } from "@/lib/links";
import { toast } from "@/lib/toast-bus";
import { useTheme } from "@/theme/theme";

const schema = z.object({
  from_email: z
    .string()
    .trim()
    .max(254)
    .refine((v) => /^\S+@\S+\.\S{2,}$/.test(v), "Enter a valid email address"),
  headline: z.string().max(300),
  phone: z.string().max(50),
  linkedin_url: z.string().max(500).refine(isOptionalWebUrl, WEB_URL_HINT),
  location: z.string().max(200),
  notice_period: z.string().max(100),
  current_ctc: z.string().max(100),
  expected_ctc: z.string().max(100),
  career_story: z.string().max(500),
  proof_1: z.string().max(200),
  proof_2: z.string().max(200),
  proof_3: z.string().max(200),
});
type Values = z.infer<typeof schema>;

function valuesFor(p: OutreachProfile): Values {
  return {
    from_email: p.from_email,
    headline: p.headline ?? "",
    phone: p.phone ?? "",
    linkedin_url: p.linkedin_url ?? "",
    location: p.location ?? "",
    notice_period: p.notice_period ?? "",
    current_ctc: p.current_ctc ?? "",
    expected_ctc: p.expected_ctc ?? "",
    career_story: p.career_story ?? "",
    proof_1: p.proof_points[0] ?? "",
    proof_2: p.proof_points[1] ?? "",
    proof_3: p.proof_points[2] ?? "",
  };
}

export function OutreachProfileSheet({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const profile = useOutreachProfile();
  return (
    <Sheet visible={visible} onClose={onClose} title="Outreach details">
      {visible && profile.data ? (
        <Body profile={profile.data} onClose={onClose} />
      ) : null}
    </Sheet>
  );
}

function Body({
  profile,
  onClose,
}: {
  profile: OutreachProfile;
  onClose: () => void;
}) {
  const { colors } = useTheme();
  const update = useUpdateOutreachProfile();
  const [error, setError] = useState<string | null>(null);
  const [india, setIndia] = useState(profile.india_style);
  const { control, handleSubmit, setValue } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: valuesFor(profile),
  });

  const submit = handleSubmit(async (v) => {
    setError(null);
    try {
      await update.mutateAsync({
        from_email: v.from_email,
        headline: v.headline,
        phone: v.phone,
        linkedin_url: normalizeWebUrl(v.linkedin_url) ?? "",
        location: v.location,
        notice_period: v.notice_period,
        current_ctc: v.current_ctc,
        expected_ctc: v.expected_ctc,
        career_story: v.career_story,
        proof_points: [v.proof_1, v.proof_2, v.proof_3]
          .map((p) => p.trim())
          .filter(Boolean),
        india_style: india,
      });
      toast.success("Outreach details saved");
      onClose();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not save. Please try again.",
      );
    }
  });

  return (
    <View style={{ gap: 10 }}>
      <Text variant="small" tone="muted">
        Used to fill and sign your messages. Leave anything blank: the draft
        shows a gap for you to fill in.
      </Text>
      {error ? <FormAlert message={error} /> : null}
      <FormText
        control={control}
        name="from_email"
        label="Send from (email)"
        keyboardType="email-address"
        autoCapitalize="none"
        hint="Signs your messages and picks the Google account for the Gmail link. A plain mail link uses your mail app's default account."
      />
      <FormText
        control={control}
        name="headline"
        label="One-line introduction"
        hint="Finish the sentence: I'm …"
      />
      {profile.suggested_headline &&
      profile.suggested_headline !== profile.headline ? (
        <Button
          label="Use the one from my resume"
          size="sm"
          variant="secondary"
          fullWidth={false}
          onPress={() => setValue("headline", profile.suggested_headline ?? "")}
        />
      ) : null}
      <FormText
        control={control}
        name="phone"
        label="Phone"
        keyboardType="phone-pad"
      />
      <FormText
        control={control}
        name="linkedin_url"
        label="LinkedIn profile link"
        autoCapitalize="none"
        keyboardType="url"
      />
      <FormText control={control} name="location" label="Current location" />
      <FormText control={control} name="notice_period" label="Notice period" />
      <FormText control={control} name="current_ctc" label="Current CTC" />
      <FormText control={control} name="expected_ctc" label="Expected CTC" />
      <FormText
        control={control}
        name="career_story"
        label="Career switch (optional)"
        multiline
        hint="One sentence that bridges your past and the role you want."
      />
      <FormText control={control} name="proof_1" label="Achievement 1" />
      <FormText control={control} name="proof_2" label="Achievement 2" />
      <FormText control={control} name="proof_3" label="Achievement 3" />
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        <Text variant="small" style={{ flex: 1 }}>
          Include India-specific messages (notice period and CTC replies)
        </Text>
        <Switch
          accessibilityLabel="Include India-specific messages"
          value={india}
          onValueChange={setIndia}
          trackColor={{ true: colors.primary, false: colors.border }}
        />
      </View>
      <Button
        label="Save"
        loading={update.isPending}
        onPress={() => void submit()}
      />
    </View>
  );
}

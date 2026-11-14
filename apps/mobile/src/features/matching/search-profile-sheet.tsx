import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { useUpdateSearchProfile, type SearchProfile } from "@/api/matching";
import { FormAlert } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { FormText } from "@/components/ui/form";
import { Sheet } from "@/components/ui/sheet";
import { toast } from "@/lib/toast-bus";

const schema = z.object({
  titles: z.string().max(400),
  locations: z.string().max(300),
  min_percent: z
    .string()
    .regex(/^\d+$/, "Enter a whole number")
    .refine((v) => Number(v) >= 30 && Number(v) <= 95, "Between 30 and 95"),
});
type Values = z.infer<typeof schema>;

const split = (text: string): string[] =>
  text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

interface Props {
  visible: boolean;
  onClose: () => void;
  profile: SearchProfile;
}

export function SearchProfileSheet({ visible, onClose, profile }: Props) {
  return (
    <Sheet visible={visible} onClose={onClose} title="What to look for">
      {visible ? <Body onClose={onClose} profile={profile} /> : null}
    </Sheet>
  );
}

function Body({ onClose, profile }: Omit<Props, "visible">) {
  const update = useUpdateSearchProfile();
  const [error, setError] = useState<string | null>(null);
  const { control, handleSubmit } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      titles: profile.title_keywords.join(", "),
      locations: profile.locations.join(", "),
      min_percent: String(Math.round(profile.min_vector_score * 100)),
    },
  });

  const submit = handleSubmit(async (v) => {
    setError(null);
    try {
      await update.mutateAsync({
        title_keywords: split(v.titles).slice(0, 6),
        locations: split(v.locations).slice(0, 5),
        min_vector_score: Number(v.min_percent) / 100,
      });
      toast.success("Search profile saved");
      onClose();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not save. Please try again.",
      );
    }
  });

  return (
    <>
      {error ? <FormAlert message={error} /> : null}
      <FormText
        control={control}
        name="titles"
        label="Job titles (comma separated)"
      />
      <FormText
        control={control}
        name="locations"
        label="Locations (comma separated)"
      />
      <FormText
        control={control}
        name="min_percent"
        label="Minimum similarity (%)"
        keyboardType="number-pad"
      />
      <Button
        label="Save"
        loading={update.isPending}
        onPress={() => void submit()}
      />
    </>
  );
}

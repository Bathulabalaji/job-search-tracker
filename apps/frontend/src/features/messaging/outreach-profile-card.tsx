import { zodResolver } from "@hookform/resolvers/zod"
import { Send } from "lucide-react"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useOutreachProfile, useUpdateOutreachProfile, type OutreachProfile } from "@/api/messaging"
import { ApiError } from "@/api/client"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

const url = z
  .string()
  .max(500)
  .refine((v) => v === "" || /^https?:\/\/\S+$/i.test(v), "Must start with http:// or https://")

const schema = z.object({
  from_email: z
    .string()
    .trim()
    .max(254)
    .refine((v) => /^\S+@\S+\.\S{2,}$/.test(v), "Enter a valid email address"),
  headline: z.string().max(300),
  phone: z.string().max(50),
  linkedin_url: url,
  location: z.string().max(200),
  notice_period: z.string().max(100),
  current_ctc: z.string().max(100),
  expected_ctc: z.string().max(100),
  career_story: z.string().max(500),
  proof_1: z.string().max(200),
  proof_2: z.string().max(200),
  proof_3: z.string().max(200),
  india_style: z.boolean(),
})
type Values = z.infer<typeof schema>

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
    india_style: p.india_style,
  }
}

/** The details that sign every message and fill its gaps. Account page. */
export function OutreachProfileCard() {
  const profile = useOutreachProfile()
  const update = useUpdateOutreachProfile()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isDirty },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: profile.data ? valuesFor(profile.data) : undefined,
  })
  useEffect(() => {
    if (profile.data) reset(valuesFor(profile.data))
  }, [profile.data, reset])

  if (!profile.data) return null
  const suggested = profile.data.suggested_headline

  const onSubmit = handleSubmit((v) =>
    update.mutate(
      {
        from_email: v.from_email,
        headline: v.headline,
        phone: v.phone,
        linkedin_url: v.linkedin_url,
        location: v.location,
        notice_period: v.notice_period,
        current_ctc: v.current_ctc,
        expected_ctc: v.expected_ctc,
        career_story: v.career_story,
        proof_points: [v.proof_1, v.proof_2, v.proof_3].map((p) => p.trim()).filter(Boolean),
        india_style: v.india_style,
      },
      {
        onSuccess: () => toast.success("Outreach details saved"),
        onError: (e) =>
          toast.error("Could not save", {
            description: e instanceof ApiError ? e.message : undefined,
          }),
      },
    ),
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Send className="size-4 text-primary" aria-hidden />
          Outreach details
        </CardTitle>
        <CardDescription>
          Used to fill and sign your follow-up emails and LinkedIn messages. Leave anything blank:
          the draft will show a gap for you to fill in.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={(e) => void onSubmit(e)} className="space-y-4" noValidate>
          <Field
            label="Send from (email)"
            hint="Signs your messages and chooses the Google account for the Gmail link. A plain mail link can't pick the sending account, so your mail app's default is used."
            error={errors.from_email?.message}
          >
            {(a11y) => (
              <Input {...a11y} {...register("from_email")} type="email" autoComplete="email" />
            )}
          </Field>
          <Field
            label="One-line introduction"
            hint="Finish the sentence: I'm …  For example: a backend engineer with 4 years of experience in Python"
            error={errors.headline?.message}
          >
            {(a11y) => <Input {...a11y} {...register("headline")} />}
          </Field>
          {suggested && suggested !== profile.data.headline ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setValue("headline", suggested, { shouldDirty: true })}
            >
              Use “{suggested}” (from your resume)
            </Button>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Phone" error={errors.phone?.message}>
              {(a11y) => <Input {...a11y} {...register("phone")} type="tel" autoComplete="tel" />}
            </Field>
            <Field label="LinkedIn profile link" error={errors.linkedin_url?.message}>
              {(a11y) => (
                <Input
                  {...a11y}
                  {...register("linkedin_url")}
                  inputMode="url"
                  placeholder="https://"
                />
              )}
            </Field>
            <Field label="Current location" error={errors.location?.message}>
              {(a11y) => <Input {...a11y} {...register("location")} />}
            </Field>
            <Field label="Notice period" error={errors.notice_period?.message}>
              {(a11y) => (
                <Input {...a11y} {...register("notice_period")} placeholder="e.g. 30 days" />
              )}
            </Field>
            <Field label="Current CTC" error={errors.current_ctc?.message}>
              {(a11y) => <Input {...a11y} {...register("current_ctc")} placeholder="e.g. 18 LPA" />}
            </Field>
            <Field label="Expected CTC" error={errors.expected_ctc?.message}>
              {(a11y) => (
                <Input {...a11y} {...register("expected_ctc")} placeholder="e.g. 24 LPA" />
              )}
            </Field>
          </div>
          <Field
            label="Career switch (optional)"
            hint="One sentence that bridges your past and the role you want, added to introductions. For example: I'm moving from QA into backend; at Acme I built our test automation framework."
            error={errors.career_story?.message}
          >
            {(a11y) => <Textarea {...a11y} {...register("career_story")} rows={2} />}
          </Field>
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">Achievements worth mentioning (up to 3)</legend>
            {(["proof_1", "proof_2", "proof_3"] as const).map((name, i) => (
              <Field key={name} label={`Achievement ${i + 1}`} error={errors[name]?.message}>
                {(a11y) => (
                  <Input
                    {...a11y}
                    {...register(name)}
                    placeholder="Cut API latency by 40% at Acme."
                  />
                )}
              </Field>
            ))}
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...register("india_style")} className="size-4" />
            Include India-specific messages (notice period and CTC replies)
          </label>
          <Button type="submit" disabled={!isDirty || update.isPending}>
            {update.isPending ? "Saving…" : "Save details"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

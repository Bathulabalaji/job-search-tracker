import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { useUpdateSearchProfile, type SearchProfile } from "@/api/matching"
import { Field } from "@/components/form/field"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

const schema = z.object({
  titles: z.string().max(400),
  locations: z.string().max(300),
  min_percent: z.coerce.number().int().min(30, "At least 30").max(95, "At most 95"),
})
type Values = z.input<typeof schema>

const split = (text: string): string[] =>
  text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)

function valuesFor(profile: SearchProfile): Values {
  return {
    titles: profile.title_keywords.join(", "),
    locations: profile.locations.join(", "),
    min_percent: Math.round(profile.min_vector_score * 100),
  }
}

export function SearchProfileDialog({
  open,
  onOpenChange,
  profile,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  profile: SearchProfile
}) {
  const update = useUpdateSearchProfile()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Values, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: valuesFor(profile),
  })
  useEffect(() => {
    if (open) reset(valuesFor(profile))
  }, [open, profile, reset])

  const onSubmit = handleSubmit((values) => {
    update.mutate(
      {
        title_keywords: split(values.titles).slice(0, 6),
        locations: split(values.locations).slice(0, 5),
        min_vector_score: values.min_percent / 100,
      },
      {
        onSuccess: () => {
          onOpenChange(false)
          toast.success("Search profile saved")
        },
        onError: (error) => toast.error("Could not save", { description: error.message }),
      },
    )
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={(event) => void onSubmit(event)} className="space-y-5" noValidate>
          <DialogHeader>
            <DialogTitle>What to look for</DialogTitle>
            <DialogDescription>
              Each refresh searches the first two titles. Starts from your resumes; change it any
              time.
            </DialogDescription>
          </DialogHeader>
          <Field label="Job titles" hint="Comma separated" error={errors.titles?.message}>
            {(a11y) => (
              <Input {...a11y} {...register("titles")} placeholder="Backend Engineer, SRE" />
            )}
          </Field>
          <Field label="Locations" hint="Comma separated" error={errors.locations?.message}>
            {(a11y) => <Input {...a11y} {...register("locations")} placeholder="Bengaluru, Pune" />}
          </Field>
          <Field
            label="Minimum similarity (%)"
            hint="Higher shows fewer, closer matches"
            error={errors.min_percent?.message}
          >
            {(a11y) => (
              <Input {...a11y} {...register("min_percent")} type="number" className="font-mono" />
            )}
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

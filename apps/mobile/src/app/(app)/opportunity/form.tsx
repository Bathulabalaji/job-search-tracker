import { zodResolver } from "@hookform/resolvers/zod"
import { Stack, useLocalSearchParams, useRouter } from "expo-router"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { View } from "react-native"

import { ApiError } from "@/api/client"
import {
  useCreateOpportunity,
  useOpportunity,
  useUpdateOpportunity,
} from "@/api/opportunities"
import { Button } from "@/components/ui/button"
import { FormDate, FormSelect, FormText } from "@/components/ui/form"
import { Screen } from "@/components/ui/screen"
import { SkeletonList } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/ui/states"
import { FormAlert } from "@/components/auth/auth-shell"
import {
  DEFAULT_VALUES,
  PRIORITY_OPTIONS,
  SOURCE_OPTIONS,
  STAGE_OPTIONS,
  WORK_MODE_OPTIONS,
  opportunitySchema,
  toCreatePayload,
  toUpdatePayload,
  valuesFromOpportunity,
  type OpportunityFormValues,
} from "@/features/pipeline/opportunity-form"
import { toast } from "@/lib/toast-bus"

export default function OpportunityFormScreen() {
  const router = useRouter()
  const params = useLocalSearchParams<{ id?: string }>()
  const editingId = params.id ? Number(params.id) : null
  const existing = useOpportunity(editingId ?? 0, editingId !== null)
  const create = useCreateOpportunity()
  const update = useUpdateOpportunity(editingId ?? 0)
  const [showMore, setShowMore] = useState(editingId !== null)
  const [formError, setFormError] = useState<string | null>(null)

  const { control, handleSubmit, reset } = useForm<OpportunityFormValues>({
    resolver: zodResolver(opportunitySchema),
    defaultValues: DEFAULT_VALUES,
  })

  useEffect(() => {
    if (existing.data) reset(valuesFromOpportunity(existing.data))
  }, [existing.data, reset])

  const saving = create.isPending || update.isPending
  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    try {
      if (editingId === null) {
        const created = await create.mutateAsync(toCreatePayload(values))
        toast.success(`Added ${created.company}`)
        router.replace({ pathname: "/opportunity/[id]", params: { id: created.id } })
      } else {
        await update.mutateAsync(toUpdatePayload(values))
        toast.success("Saved")
        router.back()
      }
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Could not save. Please try again.")
    }
  })

  if (editingId !== null && existing.isPending) {
    return (
      <Screen edges={[]}>
        <SkeletonList count={3} />
      </Screen>
    )
  }
  if (editingId !== null && existing.isError) {
    return (
      <Screen edges={[]}>
        <ErrorState error={existing.error} onRetry={() => void existing.refetch()} />
      </Screen>
    )
  }

  return (
    <Screen keyboard edges={[]} contentStyle={{ gap: 14 }}>
      <Stack.Screen options={{ title: editingId === null ? "New opportunity" : "Edit opportunity" }} />
      {formError ? <FormAlert message={formError} /> : null}

      <FormText control={control} name="company" label="Company" autoCapitalize="words" returnKeyType="next" />
      <FormText control={control} name="role" label="Role" autoCapitalize="words" />
      <FormSelect control={control} name="source" label="Source" options={SOURCE_OPTIONS} />
      <FormSelect control={control} name="priority" label="Priority" options={PRIORITY_OPTIONS} />
      {editingId === null ? (
        <FormSelect control={control} name="stage" label="Stage" options={STAGE_OPTIONS} />
      ) : null}

      {showMore ? (
        <View style={{ gap: 14 }}>
          <FormText control={control} name="location" label="Location" />
          <FormSelect control={control} name="work_mode" label="Work mode" options={WORK_MODE_OPTIONS} />
          <FormText
            control={control}
            name="fit_score"
            label="Fit score (0–100)"
            keyboardType="number-pad"
          />
          <FormText
            control={control}
            name="stack_tags"
            label="Stack tags"
            hint="Comma separated, e.g. python, fastapi"
            autoCapitalize="none"
          />
          <FormText
            control={control}
            name="jd_url"
            label="Job posting link"
            autoCapitalize="none"
            keyboardType="url"
            autoCorrect={false}
          />
          <FormText control={control} name="expected_ctc_note" label="Compensation note" />
          <FormText control={control} name="next_action" label="Next action" />
          <FormDate control={control} name="next_action_due" label="Next action due" />
          <FormText control={control} name="jd_text" label="Job description / notes" multiline />
        </View>
      ) : (
        <Button
          label="Add more details"
          icon="chevron-down"
          variant="ghost"
          onPress={() => setShowMore(true)}
        />
      )}

      <Button
        label={editingId === null ? "Add opportunity" : "Save changes"}
        loading={saving}
        onPress={() => void onSubmit()}
      />
    </Screen>
  )
}

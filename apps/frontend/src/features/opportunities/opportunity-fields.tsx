import type { Control, FieldErrors, UseFormRegister } from "react-hook-form"

import { Field, SelectField } from "@/components/form/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  PRIORITY_OPTIONS,
  SOURCE_OPTIONS,
  WORK_MODE_OPTIONS,
  type OpportunityFormValues,
} from "./opportunity-form"

interface FieldsProps {
  control: Control<OpportunityFormValues>
  register: UseFormRegister<OpportunityFormValues>
  errors: FieldErrors<OpportunityFormValues>
  /** Quick add shows only the essentials; edit shows everything. */
  full: boolean
}

export function OpportunityFields({ control, register, errors, full }: FieldsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Company" error={errors.company?.message}>
        {(a11y) => <Input {...a11y} {...register("company")} autoComplete="off" autoFocus />}
      </Field>
      <Field label="Role" error={errors.role?.message}>
        {(a11y) => <Input {...a11y} {...register("role")} autoComplete="off" />}
      </Field>
      <SelectField control={control} name="source" label="Source" options={SOURCE_OPTIONS} />
      <SelectField control={control} name="priority" label="Priority" options={PRIORITY_OPTIONS} />
      <div className="sm:col-span-2">
        <Field label="Job link" error={errors.jd_url?.message}>
          {(a11y) => (
            <Input {...a11y} {...register("jd_url")} placeholder="https://" inputMode="url" />
          )}
        </Field>
      </div>

      {full ? (
        <>
          <Field label="Location" error={errors.location?.message}>
            {(a11y) => <Input {...a11y} {...register("location")} />}
          </Field>
          <SelectField
            control={control}
            name="work_mode"
            label="Work mode"
            options={WORK_MODE_OPTIONS}
          />
          <Field label="Fit score (0-100)" error={errors.fit_score?.message}>
            {(a11y) => (
              <Input
                {...a11y}
                {...register("fit_score")}
                inputMode="numeric"
                className="font-mono"
              />
            )}
          </Field>
          <Field label="Stack tags" hint="Comma separated" error={errors.stack_tags?.message}>
            {(a11y) => (
              <Input {...a11y} {...register("stack_tags")} placeholder="python, fastapi" />
            )}
          </Field>
          <Field label="Next action" error={errors.next_action?.message}>
            {(a11y) => <Input {...a11y} {...register("next_action")} />}
          </Field>
          <Field label="Next action due" error={errors.next_action_due?.message}>
            {(a11y) => (
              <Input {...a11y} {...register("next_action_due")} type="date" className="font-mono" />
            )}
          </Field>
          <div className="sm:col-span-2">
            <Field label="Expected CTC note" error={errors.expected_ctc_note?.message}>
              {(a11y) => <Input {...a11y} {...register("expected_ctc_note")} />}
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Job description" error={errors.jd_text?.message}>
              {(a11y) => <Textarea {...a11y} {...register("jd_text")} rows={8} />}
            </Field>
          </div>
        </>
      ) : null}
    </div>
  )
}

import { useId, type ReactElement, type ReactNode } from "react"
import { Controller, type Control, type FieldPath, type FieldValues } from "react-hook-form"

import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface FieldProps {
  label: string
  error?: string | undefined
  hint?: string
  children: (props: {
    id: string
    "aria-invalid": boolean
    "aria-describedby"?: string
  }) => ReactElement
}

/** Label + control + error, wired for screen readers. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId()
  const messageId = `${id}-msg`
  const hasMessage = Boolean(error ?? hint)
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children({
        id,
        "aria-invalid": Boolean(error),
        ...(hasMessage ? { "aria-describedby": messageId } : {}),
      })}
      {hasMessage ? (
        <p
          id={messageId}
          className={error ? "text-xs text-destructive" : "text-xs text-muted-foreground"}
        >
          {error ?? hint}
        </p>
      ) : null}
    </div>
  )
}

export interface Option<V extends string> {
  value: V
  label: ReactNode
}

interface SelectFieldProps<T extends FieldValues, V extends string> {
  control: Control<T>
  name: FieldPath<T>
  label: string
  options: readonly Option<V>[]
  error?: string | undefined
}

export function SelectField<T extends FieldValues, V extends string>({
  control,
  name,
  label,
  options,
  error,
}: SelectFieldProps<T, V>) {
  return (
    <Field label={label} error={error}>
      {(a11y) => (
        <Controller
          control={control}
          name={name}
          render={({ field }) => (
            <Select
              value={typeof field.value === "string" ? field.value : ""}
              onValueChange={field.onChange}
            >
              <SelectTrigger {...a11y} className="w-full" onBlur={field.onBlur}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {options.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      )}
    </Field>
  )
}

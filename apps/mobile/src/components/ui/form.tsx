import { Controller, type Control, type FieldPath, type FieldValues } from "react-hook-form"

import { SelectField } from "./select-field"
import type { Option } from "./option-sheet"
import { TextField, type TextFieldProps } from "./text-field"
import { DateField } from "./date-field"

type FieldProps<T extends FieldValues> = {
  control: Control<T>
  name: FieldPath<T>
}

/** A TextField wired to react-hook-form; shows the zod error under the input. */
export function FormText<T extends FieldValues>({
  control,
  name,
  ...props
}: FieldProps<T> & Omit<TextFieldProps, "value" | "onChangeText" | "onBlur" | "error">) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <TextField
          {...props}
          value={typeof field.value === "string" ? field.value : String(field.value ?? "")}
          onChangeText={field.onChange}
          onBlur={field.onBlur}
          error={fieldState.error?.message}
        />
      )}
    />
  )
}

export function FormSelect<T extends FieldValues, V extends string | number>({
  control,
  name,
  label,
  options,
  placeholder,
}: FieldProps<T> & { label: string; options: readonly Option<V>[]; placeholder?: string }) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <SelectField
          label={label}
          options={options}
          placeholder={placeholder}
          value={field.value as V | null | undefined}
          onChange={field.onChange}
          error={fieldState.error?.message}
        />
      )}
    />
  )
}

export function FormDate<T extends FieldValues>({
  control,
  name,
  label,
}: FieldProps<T> & { label: string }) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <DateField
          label={label}
          value={typeof field.value === "string" ? field.value : ""}
          onChange={field.onChange}
          error={fieldState.error?.message}
        />
      )}
    />
  )
}

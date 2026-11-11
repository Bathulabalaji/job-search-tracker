import { View } from "react-native"

import { addDays, daysUntilNextMonday, formatDate } from "@/lib/format"
import { todayIso } from "@/lib/dates"
import { Chip } from "./chip"
import { Text } from "./text"
import { TextField } from "./text-field"

interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  error?: string
}

/** Quick picks for the common cases, plus a typed YYYY-MM-DD for anything else. */
export function DateField({ label, value, onChange, error }: Props) {
  const today = todayIso()
  const picks = [
    { label: "Today", date: today },
    { label: "Tomorrow", date: addDays(today, 1) },
    { label: "In 3 days", date: addDays(today, 3) },
    { label: "Next Mon", date: addDays(today, daysUntilNextMonday(today)) },
  ]
  return (
    <View style={{ gap: 8 }}>
      <TextField
        label={label}
        value={value}
        onChangeText={onChange}
        placeholder="YYYY-MM-DD"
        keyboardType="numbers-and-punctuation"
        autoCapitalize="none"
        autoCorrect={false}
        maxLength={10}
        error={error}
      />
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {picks.map((pick) => (
          <Chip
            key={pick.label}
            label={pick.label}
            selected={value === pick.date}
            onPress={() => onChange(pick.date)}
          />
        ))}
      </View>
      {/^\d{4}-\d{2}-\d{2}$/.test(value) ? (
        <Text variant="caption" tone="muted">
          {formatDate(value)}
        </Text>
      ) : null}
    </View>
  )
}

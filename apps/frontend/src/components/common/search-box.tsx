import { Search } from "lucide-react"

import { Input } from "@/components/ui/input"

interface SearchBoxProps {
  value: string
  onChange: (value: string) => void
  label: string
}

export function SearchBox({ value, onChange, label }: SearchBoxProps) {
  return (
    <div className="relative w-full sm:w-64">
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={label}
        aria-label={label}
        className="pl-9"
      />
    </div>
  )
}

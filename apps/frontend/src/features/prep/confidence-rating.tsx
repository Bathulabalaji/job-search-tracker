import { cn } from "@/lib/utils"

const LEVELS = [1, 2, 3, 4, 5] as const
const LABELS: Record<number, string> = {
  1: "Not confident",
  2: "Shaky",
  3: "Okay",
  4: "Confident",
  5: "Very confident",
}

interface ConfidenceRatingProps {
  value: number
  onChange: (value: number) => void
  label: string
}

/** Five dots as a radio group: arrow keys move, Tab leaves. Not colour-only (filled vs outlined). */
export function ConfidenceRating({ value, onChange, label }: ConfidenceRatingProps) {
  return (
    <div
      role="radiogroup"
      aria-label={`Confidence for ${label}`}
      className="flex items-center gap-1"
    >
      {LEVELS.map((level) => {
        const selected = level === value
        return (
          <button
            key={level}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`${level} of 5, ${LABELS[level]}`}
            tabIndex={selected || (value < 1 && level === 1) ? 0 : -1}
            title={`${level}/5 · ${LABELS[level]}`}
            onClick={() => onChange(level)}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight" || event.key === "ArrowUp") {
                event.preventDefault()
                onChange(Math.min(5, value + 1))
              } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
                event.preventDefault()
                onChange(Math.max(1, value - 1))
              }
            }}
            className="group rounded-full p-1.5 focus-visible:outline-2 focus-visible:outline-ring sm:p-1 [@media(pointer:coarse)]:p-2"
          >
            <span
              className={cn(
                "block size-3 rounded-full border-2 transition-colors",
                level <= value
                  ? "border-primary bg-primary"
                  : "border-muted-foreground/60 group-hover:border-primary",
              )}
            />
          </button>
        )
      })}
    </div>
  )
}

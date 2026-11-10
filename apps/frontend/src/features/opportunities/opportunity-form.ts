import { z } from "zod"

import {
  SOURCES,
  STAGES,
  WORK_MODES,
  type Opportunity,
  type OpportunityCreate,
  type OpportunityUpdate,
} from "@/api/types"
import { STAGE_LABELS, titleCase } from "@/lib/format"

const NONE = "none"

const optionalUrl = z
  .string()
  .max(1000)
  .refine(
    (value) => value === "" || /^https?:\/\/\S+$/i.test(value),
    "Must start with http:// or https://",
  )

export const opportunitySchema = z.object({
  company: z.string().trim().min(1, "Company is required").max(200),
  role: z.string().trim().min(1, "Role is required").max(200),
  source: z.enum(SOURCES),
  priority: z.enum(["1", "2", "3"]),
  stage: z.enum(STAGES),
  location: z.string().max(200),
  work_mode: z.union([z.literal(NONE), z.enum(WORK_MODES)]),
  fit_score: z.string().regex(/^(|100|[1-9]?\d)$/, "Enter a whole number from 0 to 100"),
  stack_tags: z.string().max(500),
  jd_url: optionalUrl,
  jd_text: z.string(),
  expected_ctc_note: z.string().max(500),
  next_action: z.string().max(500),
  next_action_due: z.string(),
})

export type OpportunityFormValues = z.infer<typeof opportunitySchema>

export const NO_WORK_MODE = NONE

export const DEFAULT_VALUES: OpportunityFormValues = {
  company: "",
  role: "",
  source: "linkedin",
  priority: "2",
  stage: "found",
  location: "",
  work_mode: NONE,
  fit_score: "",
  stack_tags: "",
  jd_url: "",
  jd_text: "",
  expected_ctc_note: "",
  next_action: "",
  next_action_due: "",
}

export function valuesFromOpportunity(o: Opportunity): OpportunityFormValues {
  return {
    company: o.company,
    role: o.role,
    source: o.source,
    priority: String(o.priority) as OpportunityFormValues["priority"],
    stage: o.stage,
    location: o.location ?? "",
    work_mode: o.work_mode ?? NONE,
    fit_score: o.fit_score === null ? "" : String(o.fit_score),
    stack_tags: o.stack_tags.join(", "),
    jd_url: o.jd_url ?? "",
    jd_text: o.jd_text ?? "",
    expected_ctc_note: o.expected_ctc_note ?? "",
    next_action: o.next_action ?? "",
    next_action_due: o.next_action_due ?? "",
  }
}

const orNull = (value: string): string | null => (value.trim() === "" ? null : value.trim())

function parseTags(value: string): string[] {
  const tags = value
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter((tag) => tag !== "")
  return [...new Set(tags)]
}

export function toCreatePayload(v: OpportunityFormValues): OpportunityCreate {
  return {
    company: v.company.trim(),
    role: v.role.trim(),
    source: v.source,
    stack_tags: parseTags(v.stack_tags),
    location: orNull(v.location),
    work_mode: v.work_mode === NONE ? null : v.work_mode,
    stage: v.stage,
    priority: Number(v.priority),
    fit_score: v.fit_score === "" ? null : Number(v.fit_score),
    jd_text: orNull(v.jd_text),
    jd_url: orNull(v.jd_url),
    expected_ctc_note: orNull(v.expected_ctc_note),
    next_action: orNull(v.next_action),
    next_action_due: orNull(v.next_action_due),
  }
}

export function toUpdatePayload(v: OpportunityFormValues): OpportunityUpdate {
  const { stage: _stage, ...rest } = toCreatePayload(v)
  return rest
}

export const SOURCE_OPTIONS = SOURCES.map((value) => ({ value, label: titleCase(value) }))
export const STAGE_OPTIONS = STAGES.map((value) => ({ value, label: STAGE_LABELS[value] }))
export const PRIORITY_OPTIONS = [
  { value: "1", label: "1 · High" },
  { value: "2", label: "2 · Medium" },
  { value: "3", label: "3 · Low" },
] as const
export const WORK_MODE_OPTIONS = [
  { value: NONE, label: "Not set" },
  ...WORK_MODES.map((value) => ({ value, label: titleCase(value) })),
] as const

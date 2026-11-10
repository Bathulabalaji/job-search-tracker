// Mirrors the backend Pydantic schemas (apps/backend/app/schemas).

export const STAGES = [
  "found",
  "applied",
  "screening",
  "interview_scheduled",
  "interviewing",
  "offer",
  "accepted",
  "rejected",
  "ghosted",
  "parked",
] as const
export type Stage = (typeof STAGES)[number]

export const SOURCES = ["naukri", "linkedin", "referral", "recruiter", "walkin", "other"] as const
export type Source = (typeof SOURCES)[number]

export const WORK_MODES = ["remote", "hybrid", "onsite"] as const
export type WorkMode = (typeof WORK_MODES)[number]

export const CONTACT_ROLES = ["recruiter", "hr", "manager", "referrer"] as const
export type ContactRole = (typeof CONTACT_ROLES)[number]

export const INTERACTION_TYPES = [
  "call",
  "email",
  "linkedin",
  "whatsapp",
  "interview",
  "nudge",
  "stage_change",
] as const
export type InteractionType = (typeof INTERACTION_TYPES)[number]
/** Types a person can log by hand; stage_change is written by the server on /move. */
export const LOGGABLE_INTERACTION_TYPES = INTERACTION_TYPES.filter(
  (t): t is Exclude<InteractionType, "stage_change"> => t !== "stage_change",
)

export const DIRECTIONS = ["in", "out"] as const
export type Direction = (typeof DIRECTIONS)[number]

export const FOLLOWUP_CHANNELS = ["email", "call", "linkedin", "whatsapp"] as const
export type FollowupChannel = (typeof FOLLOWUP_CHANNELS)[number]

export type FollowupStatus = "pending" | "done" | "skipped"

export interface Opportunity {
  id: number
  company: string
  role: string
  source: Source
  stack_tags: string[]
  location: string | null
  work_mode: WorkMode | null
  stage: Stage
  priority: number
  fit_score: number | null
  jd_text: string | null
  jd_url: string | null
  expected_ctc_note: string | null
  next_action: string | null
  next_action_due: string | null
  created_at: string
  updated_at: string
  last_contact_at: string | null
  days_since_contact: number
  ghosted_suggestion: boolean
}

export interface OpportunityCreate {
  company: string
  role: string
  source: Source
  stack_tags: string[]
  location: string | null
  work_mode: WorkMode | null
  stage: Stage
  priority: number
  fit_score: number | null
  jd_text: string | null
  jd_url: string | null
  expected_ctc_note: string | null
  next_action: string | null
  next_action_due: string | null
}

/** PATCH body. Stage is changed only through move. */
export type OpportunityUpdate = Partial<Omit<OpportunityCreate, "stage">>

export interface Interaction {
  id: number
  opportunity_id: number
  contact_id: number | null
  type: InteractionType
  direction: Direction
  summary: string | null
  occurred_at: string
}

export interface InteractionCreate {
  opportunity_id: number
  contact_id?: number | null
  type: InteractionType
  direction: Direction
  summary: string | null
  occurred_at?: string | null
}

export interface Followup {
  id: number
  opportunity_id: number
  due_date: string
  channel: FollowupChannel
  message_draft: string | null
  status: FollowupStatus
  done_at: string | null
}

export interface FollowupCreate {
  opportunity_id: number
  due_date: string
  channel: FollowupChannel
  message_draft: string | null
}

export type FollowupUpdate = Partial<Pick<Followup, "due_date" | "channel" | "message_draft" | "status">>

export interface Contact {
  id: number
  opportunity_id: number | null
  name: string
  role: ContactRole
  company: string | null
  email: string | null
  phone: string | null
  linkedin_url: string | null
  notes: string | null
}

export interface ContactCreate {
  opportunity_id: number | null
  name: string
  role: ContactRole
  company: string | null
  email: string | null
  phone: string | null
  linkedin_url: string | null
  notes: string | null
}

export interface MoveResponse {
  opportunity: Opportunity
  interaction: Interaction
  followup_created: Followup | null
}

export interface TodayFollowup {
  id: number
  opportunity_id: number
  company: string
  role: string
  due_date: string
  channel: FollowupChannel
  message_draft: string | null
  days_overdue: number
}

export interface TodayInterview {
  interaction_id: number
  opportunity_id: number
  company: string
  role: string
  occurred_at: string
  summary: string | null
}

export interface NextAction {
  opportunity_id: number
  company: string
  role: string
  stage: Stage
  priority: number
  next_action: string
  next_action_due: string | null
  overdue: boolean
}

export interface TodayResponse {
  today: string
  followups: TodayFollowup[]
  interviews: TodayInterview[]
  next_actions: NextAction[]
}

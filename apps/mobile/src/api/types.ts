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
] as const;
export type Stage = (typeof STAGES)[number];

export const SOURCES = [
  "naukri",
  "linkedin",
  "referral",
  "recruiter",
  "walkin",
  "other",
] as const;
export type Source = (typeof SOURCES)[number];

export const WORK_MODES = ["remote", "hybrid", "onsite"] as const;
export type WorkMode = (typeof WORK_MODES)[number];

export const CONTACT_ROLES = [
  "recruiter",
  "hr",
  "manager",
  "referrer",
] as const;
export type ContactRole = (typeof CONTACT_ROLES)[number];

export const INTERACTION_TYPES = [
  "call",
  "email",
  "linkedin",
  "whatsapp",
  "interview",
  "nudge",
  "stage_change",
] as const;
export type InteractionType = (typeof INTERACTION_TYPES)[number];
/** Types a person can log by hand; stage_change is written by the server on /move. */
export const LOGGABLE_INTERACTION_TYPES = INTERACTION_TYPES.filter(
  (t): t is Exclude<InteractionType, "stage_change"> => t !== "stage_change",
);

export const DIRECTIONS = ["in", "out"] as const;
export type Direction = (typeof DIRECTIONS)[number];

export const FOLLOWUP_CHANNELS = [
  "email",
  "call",
  "linkedin",
  "whatsapp",
] as const;
export type FollowupChannel = (typeof FOLLOWUP_CHANNELS)[number];

export type FollowupStatus = "pending" | "done" | "skipped";

export interface Opportunity {
  id: number;
  company: string;
  role: string;
  source: Source;
  stack_tags: string[];
  location: string | null;
  work_mode: WorkMode | null;
  stage: Stage;
  priority: number;
  fit_score: number | null;
  jd_text: string | null;
  jd_url: string | null;
  expected_ctc_note: string | null;
  next_action: string | null;
  next_action_due: string | null;
  created_at: string;
  updated_at: string;
  last_contact_at: string | null;
  days_since_contact: number;
  ghosted_suggestion: boolean;
}

export interface OpportunityCreate {
  company: string;
  role: string;
  source: Source;
  stack_tags: string[];
  location: string | null;
  work_mode: WorkMode | null;
  stage: Stage;
  priority: number;
  fit_score: number | null;
  jd_text: string | null;
  jd_url: string | null;
  expected_ctc_note: string | null;
  next_action: string | null;
  next_action_due: string | null;
}

/** PATCH body. Stage is changed only through move. */
export type OpportunityUpdate = Partial<Omit<OpportunityCreate, "stage">>;

export interface Interaction {
  id: number;
  opportunity_id: number;
  contact_id: number | null;
  type: InteractionType;
  direction: Direction;
  summary: string | null;
  occurred_at: string;
}

export interface InteractionCreate {
  opportunity_id: number;
  contact_id?: number | null;
  type: InteractionType;
  direction: Direction;
  summary: string | null;
  occurred_at?: string | null;
}

export interface Followup {
  id: number;
  opportunity_id: number;
  due_date: string;
  channel: FollowupChannel;
  message_draft: string | null;
  status: FollowupStatus;
  done_at: string | null;
}

export interface FollowupCreate {
  opportunity_id: number;
  due_date: string;
  channel: FollowupChannel;
  message_draft: string | null;
}

export type FollowupUpdate = Partial<
  Pick<Followup, "due_date" | "channel" | "message_draft" | "status">
>;

export interface Contact {
  id: number;
  opportunity_id: number | null;
  name: string;
  role: ContactRole;
  company: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  notes: string | null;
}

export interface ContactCreate {
  opportunity_id: number | null;
  name: string;
  role: ContactRole;
  company: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  notes: string | null;
}

export interface MoveResponse {
  opportunity: Opportunity;
  interaction: Interaction;
  followup_created: Followup | null;
}

export interface TodayFollowup {
  id: number;
  opportunity_id: number;
  company: string;
  role: string;
  due_date: string;
  channel: FollowupChannel;
  message_draft: string | null;
  days_overdue: number;
}

export interface TodayInterview {
  interaction_id: number;
  opportunity_id: number;
  company: string;
  role: string;
  occurred_at: string;
  summary: string | null;
}

export interface NextAction {
  opportunity_id: number;
  company: string;
  role: string;
  stage: Stage;
  priority: number;
  next_action: string;
  next_action_due: string | null;
  overdue: boolean;
}

export interface TodayResponse {
  today: string;
  followups: TodayFollowup[];
  interviews: TodayInterview[];
  next_actions: NextAction[];
}

// ---- Daily logs, targets, prep, analytics -------------------------------------------------

export interface DailyLog {
  id: number;
  log_date: string;
  applications_sent: number;
  messages_sent: number;
  referrals_requested: number;
  problems_solved: number;
  mocks_done: number;
  hours_prep: number;
  notes: string | null;
}

export type DailyLogCounts = Omit<DailyLog, "id" | "log_date" | "notes">;

export interface DailyLogCreate extends DailyLogCounts {
  log_date: string;
  notes?: string | null;
}

export type DailyLogUpdate = Partial<DailyLogCounts> & {
  notes?: string | null;
};

export interface Streak {
  today: string;
  current: number;
  longest: number;
  logged_today: boolean;
  last_active_date: string | null;
}

export interface WeeklyTarget {
  id: number;
  week_start: string;
  applications: number;
  messages: number;
  referrals: number;
  problems: number;
  mocks: number;
  interviews: number;
}

export type WeeklyTargetValues = Omit<WeeklyTarget, "id" | "week_start">;
export type WeeklyTargetCreate = WeeklyTargetValues & { week_start: string };

export const PREP_CATEGORIES = [
  "python",
  "fastapi",
  "db",
  "react",
  "ai",
  "system-design",
  "behavioral",
] as const;
export type PrepCategory = (typeof PREP_CATEGORIES)[number];

export const PREP_STATUSES = ["todo", "doing", "done"] as const;
export type PrepStatus = (typeof PREP_STATUSES)[number];

export interface PrepItem {
  id: number;
  topic: string;
  category: PrepCategory;
  status: PrepStatus;
  confidence: number;
  notes: string | null;
}

export interface PrepItemCreate {
  topic: string;
  category: PrepCategory;
  status: PrepStatus;
  confidence: number;
  notes: string | null;
}

export type PrepItemUpdate = Partial<PrepItemCreate>;

export type Metric =
  | "applications"
  | "messages"
  | "referrals"
  | "problems"
  | "mocks"
  | "interviews";

export interface WeeklyTotals {
  applications: number;
  messages: number;
  referrals: number;
  problems: number;
  mocks: number;
  interviews: number;
  hours_prep: number;
}

export interface MetricProgress {
  metric: Metric;
  label: string;
  actual: number;
  target: number | null;
  percent: number | null;
}

export interface DailyPoint {
  date: string;
  applications: number;
  messages: number;
  referrals: number;
  problems: number;
  mocks: number;
  hours_prep: number;
}

export interface WeekTrendPoint {
  week_start: string;
  applications: number;
  messages: number;
  referrals: number;
  problems: number;
  mocks: number;
  interviews: number;
}

export interface FunnelStep {
  key: string;
  label: string;
  count: number;
  conversion_from_previous: number | null;
  conversion_from_start: number | null;
}

export interface SourceResponse {
  source: Source;
  applied: number;
  responded: number;
  response_rate: number | null;
}

export interface Scorecard {
  applications_total: number;
  response_rate: number | null;
  interview_rate: number | null;
  offers: number;
  active_opportunities: number;
  current_streak: number;
}

export interface WeeklyAnalytics {
  week_start: string;
  week_end: string;
  is_current_week: boolean;
  target: WeeklyTarget | null;
  target_carried_over: boolean;
  totals: WeeklyTotals;
  progress: MetricProgress[];
  daily: DailyPoint[];
  trend: WeekTrendPoint[];
  funnel: FunnelStep[];
  response_by_source: SourceResponse[];
  scorecard: Scorecard;
}

// ---- Resumes -------------------------------------------------------------------------------

export interface ResumeProfile {
  titles: string[];
  years_experience: number | null;
  skills: { name: string; years: number | null }[];
  domains: string[];
  education: string[];
  locations: string[];
  notable_projects: string[];
  summary: string;
}

/** The uploaded PDF: where it stands in extraction and indexing. */
export interface ResumeDocument {
  file_name: string | null;
  content_type: string | null;
  size_bytes: number | null;
  page_count: number | null;
  uploaded_at: string | null;
  text_status: "none" | "ready" | "failed";
  embed_status: "none" | "pending" | "ready" | "failed";
  processing_error: string | null;
  profile: ResumeProfile | null;
}

export interface Resume {
  id: number;
  label: string;
  focus: string | null;
  file_name: string | null;
  version: string;
  notes: string | null;
  document: ResumeDocument | null;
}

export type ResumeCreate = Omit<Resume, "id" | "document">;
export type ResumeUpdate = Partial<ResumeCreate>;

export type ContactUpdate = Partial<ContactCreate>;

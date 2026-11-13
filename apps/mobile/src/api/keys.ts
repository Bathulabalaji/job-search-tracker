export interface OpportunityFilters {
  priority?: number
  source?: string
  q?: string
}

export const queryKeys = {
  opportunities: {
    all: ["opportunities"] as const,
    list: (filters: OpportunityFilters) => ["opportunities", "list", filters] as const,
    lists: ["opportunities", "list"] as const,
    detail: (id: number) => ["opportunities", "detail", id] as const,
  },
  interactions: (opportunityId: number) => ["interactions", opportunityId] as const,
  followups: (opportunityId: number) => ["followups", opportunityId] as const,
  contacts: (opportunityId: number) => ["contacts", opportunityId] as const,
  contactsList: (filters: { q?: string; role?: string }) => ["contacts", "list", filters] as const,
  contactsAll: ["contacts"] as const,
  resumes: (q: string) => ["resumes", q] as const,
  resumesAll: ["resumes"] as const,
  dashboardToday: ["dashboard", "today"] as const,
  dailyLogs: {
    all: ["daily-logs"] as const,
    range: (from: string, to: string) => ["daily-logs", "range", from, to] as const,
    streak: ["daily-logs", "streak"] as const,
  },
  weeklyTargets: ["weekly-targets"] as const,
  analyticsWeekly: (weekOf: string | undefined) =>
    ["analytics", "weekly", weekOf ?? "current"] as const,
  analytics: ["analytics"] as const,
  prepItems: ["prep-items"] as const,
  chat: {
    all: ["chat"] as const,
    config: ["chat", "config"] as const,
    conversations: ["chat", "conversations"] as const,
    conversation: (id: number) => ["chat", "conversation", id] as const,
  },
}

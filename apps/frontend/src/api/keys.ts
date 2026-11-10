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
  dashboardToday: ["dashboard", "today"] as const,
}

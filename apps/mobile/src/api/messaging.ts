import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { request } from "./client";
import { queryKeys } from "./keys";
import type { ContactRole, Stage } from "./types";

export type OutreachChannel = "email" | "linkedin" | "linkedin_note";
export type SentChannel = "email" | "linkedin";

// ---- the sender ---------------------------------------------------------------------------

export interface OutreachProfile {
  /** The address messages come from: the saved one, or the account email. */
  from_email: string;
  headline: string | null;
  phone: string | null;
  linkedin_url: string | null;
  location: string | null;
  notice_period: string | null;
  current_ctc: string | null;
  expected_ctc: string | null;
  career_story: string | null;
  proof_points: string[];
  india_style: boolean;
  suggested_headline: string | null;
}

export type OutreachProfileUpdate = Partial<
  Omit<OutreachProfile, "suggested_headline">
>;

export function useOutreachProfile() {
  return useQuery({
    queryKey: queryKeys.messaging.profile,
    queryFn: () => request<OutreachProfile>("/messages/profile"),
    staleTime: 60_000,
  });
}

export function useUpdateOutreachProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: OutreachProfileUpdate) =>
      request<OutreachProfile>("/messages/profile", { method: "PUT", body }),
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.messaging.profile, profile);
      // The India setting decides which templates are listed.
      void queryClient.invalidateQueries({
        queryKey: queryKeys.messaging.templates,
      });
    },
  });
}

// ---- templates ----------------------------------------------------------------------------

export interface TemplateVariant {
  channel: OutreachChannel;
  subject: string | null;
  body: string;
  edited: boolean;
  template_id: number | null;
}

export interface MessageTemplate {
  /** "sys:follow_up_1" for a built-in, "usr:12" for one the user wrote. */
  key: string;
  source: "system" | "custom";
  group: string;
  group_label: string;
  name: string;
  summary: string;
  stages: Stage[];
  recipients: ContactRole[];
  india_only: boolean;
  tips: string[];
  variants: TemplateVariant[];
  archived: boolean;
}

export interface TemplateCreate {
  name: string;
  channel: OutreachChannel;
  subject: string | null;
  body: string;
  stages?: Stage[];
  recipient_roles?: ContactRole[];
  /** Make an editable copy of a built-in template. */
  base_key?: string;
}

export type TemplateUpdate = Partial<
  Pick<TemplateCreate, "name" | "subject" | "body">
> & {
  archived?: boolean;
};

export function useTemplates() {
  return useQuery({
    queryKey: queryKeys.messaging.templates,
    queryFn: () => request<MessageTemplate[]>("/messages/templates"),
    staleTime: 60_000,
  });
}

function useInvalidateTemplates() {
  const queryClient = useQueryClient();
  return () =>
    void queryClient.invalidateQueries({
      queryKey: queryKeys.messaging.templates,
    });
}

export function useCreateTemplate() {
  const invalidate = useInvalidateTemplates();
  return useMutation({
    mutationFn: (body: TemplateCreate) =>
      request<MessageTemplate>("/messages/templates", { method: "POST", body }),
    onSuccess: invalidate,
  });
}

export function useUpdateTemplate() {
  const invalidate = useInvalidateTemplates();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: TemplateUpdate }) =>
      request<MessageTemplate>(`/messages/templates/${id}`, {
        method: "PATCH",
        body: patch,
      }),
    onSuccess: invalidate,
  });
}

export function useDeleteTemplate() {
  const invalidate = useInvalidateTemplates();
  return useMutation({
    mutationFn: (id: number) =>
      request<void>(`/messages/templates/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

// ---- drafting for one opportunity ---------------------------------------------------------

export interface ContactChoice {
  id: number;
  name: string;
  role: ContactRole;
  email: string | null;
  linkedin_url: string | null;
  last_messaged_days: number | null;
}

export interface Suggestion {
  kind: "send" | "wait" | "stop" | "add_contact";
  template_key: string | null;
  channel: OutreachChannel | null;
  contact_id: number | null;
  title: string;
  reason: string;
  due: boolean;
}

export interface Suggestions {
  suggestions: Suggestion[];
  contacts: ContactChoice[];
}

export interface MissingField {
  name: string;
  label: string;
}

export interface AttachHint {
  resume_id: number;
  label: string;
  score: number | null;
  has_file: boolean;
}

export interface MessagePreview {
  template_key: string;
  template_name: string;
  channel: OutreachChannel;
  to: string | null;
  to_name: string | null;
  from_email: string;
  subject: string | null;
  body: string;
  missing: MissingField[];
  char_count: number;
  char_limit: number | null;
  warnings: string[];
  tips: string[];
  attach: AttachHint | null;
  edited: boolean;
}

export interface SentMessage {
  id: number;
  opportunity_id: number;
  contact_id: number | null;
  template_key: string;
  channel: SentChannel;
  subject: string | null;
  body: string;
  sent_at: string;
  replied_at: string | null;
  template_name?: string | null;
}

export interface SentResult {
  message: SentMessage;
  followup_closed_id: number | null;
  next_followup_id: number | null;
  next_followup_due: string | null;
  already_recorded: boolean;
}

export interface PolishResult {
  subject: string | null;
  body: string;
  changed: boolean;
  notice: string | null;
}

export type PolishInstruction =
  "shorter" | "warmer" | "more_formal" | "more_direct" | "fix_grammar";

export function useSuggestions(opportunityId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.messaging.suggestions(opportunityId),
    queryFn: () =>
      request<Suggestions>(
        `/opportunities/${opportunityId}/messages/suggestions`,
      ),
    enabled,
  });
}

export function usePreview(
  opportunityId: number,
  templateKey: string | null,
  channel: OutreachChannel,
  contactId: number | null,
) {
  return useQuery({
    queryKey: queryKeys.messaging.preview(
      opportunityId,
      templateKey ?? "",
      channel,
      contactId,
    ),
    queryFn: () =>
      request<MessagePreview>(
        `/opportunities/${opportunityId}/messages/preview`,
        {
          method: "POST",
          body: { template_key: templateKey, channel, contact_id: contactId },
        },
      ),
    enabled: templateKey !== null,
    placeholderData: keepPreviousData,
    staleTime: 0,
    gcTime: 0, // a draft is never reused: values and the clock move on
  });
}

export function usePolish(opportunityId: number) {
  return useMutation({
    mutationFn: (body: {
      subject: string | null;
      body: string;
      instruction: PolishInstruction;
    }) =>
      request<PolishResult>(`/opportunities/${opportunityId}/messages/polish`, {
        method: "POST",
        body,
      }),
  });
}

export function useSentMessages(opportunityId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.messaging.sent(opportunityId),
    queryFn: () =>
      request<SentMessage[]>(`/opportunities/${opportunityId}/messages`),
    enabled,
  });
}

/** Refetch everything a recorded message changes: the timeline, follow-ups and Today. */
function useRefreshAfterSend(opportunityId: number) {
  const queryClient = useQueryClient();
  return () => {
    for (const key of [
      queryKeys.messaging.suggestions(opportunityId),
      queryKeys.messaging.sent(opportunityId),
      queryKeys.messaging.stats,
      queryKeys.interactions(opportunityId),
      queryKeys.followups(opportunityId),
      queryKeys.dashboardToday,
      queryKeys.opportunities.detail(opportunityId),
    ]) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
    void queryClient.invalidateQueries({
      queryKey: queryKeys.opportunities.lists,
    });
  };
}

export function useMarkSent(opportunityId: number) {
  const refresh = useRefreshAfterSend(opportunityId);
  return useMutation({
    mutationFn: (body: {
      template_key: string;
      channel: SentChannel;
      contact_id: number | null;
      subject: string | null;
      body: string;
      schedule_next: boolean;
      request_id: string;
    }) =>
      request<SentResult>(`/opportunities/${opportunityId}/messages/sent`, {
        method: "POST",
        body,
      }),
    onSuccess: refresh,
  });
}

export function useMarkReplied(opportunityId: number) {
  const refresh = useRefreshAfterSend(opportunityId);
  return useMutation({
    mutationFn: (messageId: number) =>
      request<SentMessage>(`/messages/${messageId}/replied`, {
        method: "POST",
      }),
    onSuccess: refresh,
  });
}

// ---- results ------------------------------------------------------------------------------

export interface MessageStatRow {
  key: string;
  name: string;
  channel: string;
  sent: number;
  replied: number;
  reply_rate: number;
}

export interface MessageStats {
  sent: number;
  replied: number;
  reply_rate: number;
  by_template: MessageStatRow[];
}

export function useMessageStats() {
  return useQuery({
    queryKey: queryKeys.messaging.stats,
    queryFn: () => request<MessageStats>("/messages/stats"),
  });
}

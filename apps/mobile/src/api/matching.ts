import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { JobCardData } from "./chat";
import { request } from "./client";
import { queryKeys } from "./keys";

export interface ResumeMatch {
  resume_id: number;
  label: string;
  /** Mean cosine similarity of the resume's best passages to the JD, 0-1. */
  vector_score: number | null;
  /** The model's 0-100 rubric score. */
  score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  suggestions: string[];
}

export interface MatchResult {
  target: "opportunity" | "posting";
  target_id: number;
  target_label: string;
  best_resume_id: number | null;
  per_resume: ResumeMatch[];
  jd_source: "opportunity" | "posting";
  cached: boolean;
  model: string | null;
}

/** The stored result for this opportunity, without spending anything. */
export function useStoredMatch(opportunityId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.matching(opportunityId),
    queryFn: () =>
      request<MatchResult | null>(`/opportunities/${opportunityId}/match`),
    enabled,
    staleTime: 60_000,
  });
}

export function useRunMatch(opportunityId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (force: boolean) =>
      request<MatchResult>(`/opportunities/${opportunityId}/match`, {
        method: "POST",
        body: { force },
      }),
    onSuccess: (result) =>
      queryClient.setQueryData(queryKeys.matching(opportunityId), result),
  });
}

// ---- Jobs for you ---------------------------------------------------------------------------

export interface Recommendation {
  id: number;
  job: JobCardData;
  vector_score: number;
  best_resume_id: number | null;
  best_resume_label: string | null;
  created_at: string;
}

export interface SearchProfile {
  title_keywords: string[];
  locations: string[];
  work_modes: string[];
  min_vector_score: number;
  enabled: boolean;
  last_refreshed_at: string | null;
}

export type SearchProfileUpdate = Partial<
  Omit<SearchProfile, "last_refreshed_at">
>;

export interface RefreshResult {
  added: number;
  considered: number;
  notices: { code: string; message: string }[];
}

export function useRecommendations() {
  return useQuery({
    queryKey: queryKeys.recommendations.feed,
    queryFn: () =>
      request<Recommendation[]>("/recommendations", { params: { limit: 20 } }),
  });
}

export function useRefreshRecommendations() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      request<RefreshResult>("/recommendations/refresh", { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.recommendations.all,
      });
    },
  });
}

export function useDismissRecommendation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      request<void>(`/recommendations/${id}/dismiss`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.recommendations.feed,
      });
    },
  });
}

export function useSearchProfile() {
  return useQuery({
    queryKey: queryKeys.recommendations.profile,
    queryFn: () => request<SearchProfile>("/recommendations/profile"),
  });
}

export function useUpdateSearchProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SearchProfileUpdate) =>
      request<SearchProfile>("/recommendations/profile", {
        method: "PUT",
        body,
      }),
    onSuccess: (profile) =>
      queryClient.setQueryData(queryKeys.recommendations.profile, profile),
  });
}

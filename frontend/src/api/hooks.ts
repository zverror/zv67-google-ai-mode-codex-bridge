import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  setCsrf,
  type Account,
  type AuditRow,
  type AuthStatus,
  type ModelInfo,
  type Overview,
  type RequestRow,
  type SessionRow,
  type SettingsInfo,
  type Summary,
  type SystemInfo,
  type TimeBucket,
} from "./client";

export function useAuthStatus() {
  return useQuery({
    queryKey: ["auth"],
    queryFn: async () => {
      const status = await api<AuthStatus>("/auth/status");
      if (status.authenticated && status.csrf_token) {
        setCsrf(status.csrf_token);
      }
      return status;
    },
  });
}

export function useOverview() {
  return useQuery({ queryKey: ["overview"], queryFn: () => api<Overview>("/overview") });
}

export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: () => api<Account[]>("/accounts") });
}

export function useModels() {
  return useQuery({ queryKey: ["models"], queryFn: () => api<ModelInfo[]>("/models") });
}

export function useSummary(hours = 24) {
  return useQuery({
    queryKey: ["stats", hours],
    queryFn: () => api<Summary>(`/stats?hours=${hours}`),
  });
}

export function useTimeseries(hours = 24, bucketMinutes = 60) {
  return useQuery({
    queryKey: ["timeseries", hours, bucketMinutes],
    queryFn: () =>
      api<TimeBucket[]>(`/stats/timeseries?hours=${hours}&bucket_minutes=${bucketMinutes}`),
  });
}

export function useRequests(limit = 100) {
  return useQuery({
    queryKey: ["requests", limit],
    queryFn: () => api<RequestRow[]>(`/requests?limit=${limit}`),
    refetchInterval: 5000,
  });
}

export function useSessions() {
  return useQuery({ queryKey: ["sessions"], queryFn: () => api<SessionRow[]>("/sessions") });
}

export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsInfo>("/settings") });
}

export function useSystem() {
  return useQuery({ queryKey: ["system"], queryFn: () => api<SystemInfo>("/system") });
}

export function useAudit() {
  return useQuery({ queryKey: ["audit"], queryFn: () => api<AuditRow[]>("/audit") });
}

export function useInvalidateAll() {
  const client = useQueryClient();
  return () => client.invalidateQueries();
}


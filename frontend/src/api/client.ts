export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const CSRF_KEY = "zv67_csrf";

export function setCsrf(token: string | null) {
  if (token) {
    sessionStorage.setItem(CSRF_KEY, token);
  } else {
    sessionStorage.removeItem(CSRF_KEY);
  }
}

export function getCsrf(): string {
  return sessionStorage.getItem(CSRF_KEY) ?? "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const csrf = getCsrf();
  if (csrf) {
    headers.set("X-ZV67-CSRF", csrf);
  }
  const response = await fetch(`/admin/api${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const error = (payload as { error?: { message?: string; code?: string } } | null)?.error;
    if (response.status === 401) {
      window.dispatchEvent(new Event("zv67-unauthorized"));
    }
    throw new ApiError(
      response.status,
      error?.message ?? `Ошибка HTTP ${response.status}`,
      error?.code,
    );
  }
  return payload as T;
}

export type CapabilityStatus =
  | "VERIFIED"
  | "EXPERIMENTAL"
  | "UNSUPPORTED"
  | "NOT TESTED";

export interface AuthStatus {
  configured: boolean;
  authenticated: boolean;
  csrf_token: string | null;
}

export interface Summary {
  period_hours: number;
  requests: number;
  successes: number;
  errors: number;
  active: number;
  success_rate: number | null;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  by_model: Record<string, number>;
  by_account: Record<string, number>;
}

export interface Overview {
  service: {
    status: string;
    version: string;
    provider: string;
    provider_status: string;
    mock: boolean;
  };
  accounts: { total: number; enabled: number };
  summary: Summary;
  routing_strategy: string;
}

export interface Account {
  id: string;
  display_name: string;
  subscription_status: string;
  enabled: boolean;
  connection_status: string;
  concurrency_limit: number;
  routing_weight: number;
  last_success_at: string | null;
  last_error: string | null;
  created_at: string;
  has_credentials: boolean;
  active_requests: number;
  in_cooldown: boolean;
  statistics: {
    requests: number;
    successes: number;
    errors: number;
    avg_latency_ms: number | null;
    session_count: number;
  };
}

export interface ModelInfo {
  id: string;
  display_name: string;
  provider: string;
  upstream: string;
  capabilities: Record<string, CapabilityStatus>;
}

export interface RequestRow {
  id: string;
  session_id: string | null;
  account_id: string | null;
  model_id: string;
  backend: string;
  status: string;
  http_status: number | null;
  error_code: string | null;
  latency_ms: number | null;
  retry_count: number;
  tool_call_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface SessionRow {
  id: string;
  account_id: string | null;
  external_thread_id: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  turn_count: number;
}

export interface TimeBucket {
  bucket: string;
  requests: number;
  successes: number;
  errors: number;
  avg_latency_ms: number | null;
}

export interface AuditRow {
  id: number;
  action: string;
  target: string | null;
  detail: string | null;
  created_at: string;
}

export interface SystemInfo {
  version: string;
  python: string;
  platform: string;
  database_path: string;
  data_dir: string;
  provider: string;
  mock: boolean;
  master_key_store: string;
  routing_strategy: string;
}

export interface SettingsInfo {
  routing_strategy: string;
  session_ttl_hours: number;
  max_messages: number;
  max_message_chars: number;
  host: string;
  port: number;
  api_key_configured: boolean;
}


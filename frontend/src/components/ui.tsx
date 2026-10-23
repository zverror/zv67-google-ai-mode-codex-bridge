import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-2xl border p-5 shadow-sm ${className}`}
      style={{ background: "var(--panel)", borderColor: "var(--border)" }}
    >
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? (
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {subtitle}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "ok" | "warn" | "bad";
}) {
  const color =
    tone === "ok" ? "var(--ok)" : tone === "warn" ? "var(--warn)" : tone === "bad" ? "var(--bad)" : "var(--fg)";
  return (
    <Card>
      <div className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--muted)" }}>
        {label}
      </div>
      <div className="mt-2 text-3xl font-semibold" style={{ color }}>
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          {hint}
        </div>
      ) : null}
    </Card>
  );
}

const TONES: Record<string, string> = {
  ok: "var(--ok)",
  warn: "var(--warn)",
  bad: "var(--bad)",
  neutral: "var(--muted)",
};

export function toneFor(status: string): keyof typeof TONES {
  const value = status.toUpperCase();
  if (["VERIFIED", "ACTIVE", "SUCCESS", "OK", "COMPLETED"].includes(value)) return "ok";
  if (["EXPERIMENTAL", "COOLDOWN", "DEGRADED", "STARTED", "PENDING", "UNKNOWN"].includes(value))
    return "warn";
  if (["UNSUPPORTED", "ERROR", "UNAUTHORIZED", "DISABLED", "CANCELLED"].includes(value)) return "bad";
  return "neutral";
}

export function Badge({ children, status }: { children?: ReactNode; status?: string }) {
  const tone = toneFor(status ?? String(children ?? ""));
  const color = TONES[tone];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ color, background: "color-mix(in srgb, " + color + " 14%, transparent)" }}
    >
      {children ?? status}
    </span>
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  className?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const style =
    variant === "primary"
      ? { background: "var(--accent)", color: "#fff" }
      : variant === "danger"
        ? { background: "color-mix(in srgb, var(--bad) 16%, transparent)", color: "var(--bad)" }
        : { background: "transparent", color: "var(--fg)", border: "1px solid var(--border)" };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${className}`}
      style={style}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      {children}
      {hint ? (
        <span className="mt-1 block text-xs" style={{ color: "var(--muted)" }}>
          {hint}
        </span>
      ) : null}
    </label>
  );
}

export const inputClass =
  "w-full rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)]/40";

export function inputStyle() {
  return {
    background: "var(--panel-2)",
    borderColor: "var(--border)",
    color: "var(--fg)",
  } as const;
}

export function Spinner() {
  return (
    <div className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
      <span className="pulse-soft inline-block h-2 w-2 rounded-full" style={{ background: "var(--accent)" }} />
      Загрузка…
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div
      className="rounded-xl border px-4 py-3 text-sm"
      style={{ borderColor: "var(--bad)", color: "var(--bad)", background: "color-mix(in srgb, var(--bad) 8%, transparent)" }}
    >
      {error instanceof Error ? error.message : "Неизвестная ошибка"}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="py-10 text-center text-sm" style={{ color: "var(--muted)" }}>
      {children}
    </div>
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function ms(value: number | null): string {
  return value === null ? "—" : `${value} мс`;
}


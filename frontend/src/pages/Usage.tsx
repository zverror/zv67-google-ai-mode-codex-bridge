import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRequests, useSummary, useTimeseries } from "../api/hooks";
import { Card, Empty, ErrorBox, PageHeader, Spinner, Stat, inputClass, inputStyle, ms, percent } from "../components/ui";

const PERIODS = [
  { value: 1, label: "1 час" },
  { value: 24, label: "24 часа" },
  { value: 168, label: "7 дней" },
  { value: 720, label: "30 дней" },
];

export default function Usage() {
  const [hours, setHours] = useState(24);
  const summary = useSummary(hours);
  const series = useTimeseries(hours, hours <= 24 ? 60 : 1440);
  const requests = useRequests(500);

  if (summary.isLoading) return <Spinner />;
  if (summary.error) return <ErrorBox error={summary.error} />;
  const data = summary.data;
  if (!data) return null;

  const chart = (series.data ?? []).map((point) => ({
    ...point,
    label:
      hours <= 24
        ? new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(new Date(point.bucket))
        : new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(new Date(point.bucket)),
  }));

  function exportAs(format: "json" | "csv") {
    const rows = requests.data ?? [];
    let content = "";
    let type = "application/json";
    if (format === "json") {
      content = JSON.stringify(rows, null, 2);
    } else {
      type = "text/csv";
      const header = ["id", "created_at", "model_id", "account_id", "status", "http_status", "latency_ms", "error_code"];
      content = [header.join(","), ...rows.map((row) => header.map((key) => JSON.stringify(row[key as keyof typeof row] ?? "")).join(","))].join("\n");
    }
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `zv67-requests.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader
        title="Статистика"
        subtitle="Метрики собираются локально; токены Google не выдумываются"
        action={
          <div className="flex gap-2">
            <select
              className={inputClass}
              style={inputStyle()}
              value={hours}
              onChange={(event) => setHours(Number(event.target.value))}
            >
              {PERIODS.map((period) => (
                <option key={period.value} value={period.value}>
                  {period.label}
                </option>
              ))}
            </select>
          </div>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Запросов" value={data.requests} />
        <Stat label="Успешность" value={percent(data.success_rate)} tone="ok" />
        <Stat label="p50 / p95" value={`${data.p50_latency_ms ?? "—"} / ${data.p95_latency_ms ?? "—"} мс`} />
        <Stat label="Ошибок" value={data.errors} tone={data.errors ? "bad" : undefined} hint={ms(data.avg_latency_ms)} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold">Активность</h2>
          {chart.length === 0 ? (
            <Empty>Нет данных за период</Empty>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="var(--muted)" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} stroke="var(--muted)" width={28} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--panel)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="successes" name="Успешно" stackId="a" fill="#4ade80" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="errors" name="Ошибки" stackId="a" fill="#f87171" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold">Экспорт</h2>
          <p className="mb-3 text-xs" style={{ color: "var(--muted)" }}>
            Выгружаются только метаданные запросов: без промптов, cookies и содержимого ответов.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => exportAs("csv")}
              className="rounded-xl border px-3 py-2 text-sm"
              style={{ borderColor: "var(--border)" }}
            >
              CSV
            </button>
            <button
              onClick={() => exportAs("json")}
              className="rounded-xl border px-3 py-2 text-sm"
              style={{ borderColor: "var(--border)" }}
            >
              JSON
            </button>
          </div>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <Breakdown title="По моделям" values={data.by_model} />
        <Breakdown title="По аккаунтам" values={data.by_account} />
      </div>
    </div>
  );
}

function Breakdown({ title, values }: { title: string; values: Record<string, number> }) {
  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {Object.keys(values).length === 0 ? (
        <Empty>Нет данных</Empty>
      ) : (
        <div className="space-y-2 text-sm">
          {Object.entries(values)
            .sort((a, b) => b[1] - a[1])
            .map(([key, count]) => (
              <div key={key} className="flex items-center justify-between gap-3">
                <span className="truncate">{key}</span>
                <span style={{ color: "var(--muted)" }}>{count}</span>
              </div>
            ))}
        </div>
      )}
    </Card>
  );
}


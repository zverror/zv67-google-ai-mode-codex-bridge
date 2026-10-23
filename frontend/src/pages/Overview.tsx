import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useOverview, useRequests, useTimeseries } from "../api/hooks";
import {
  Badge,
  Card,
  Empty,
  ErrorBox,
  PageHeader,
  Spinner,
  Stat,
  formatDate,
  ms,
  percent,
} from "../components/ui";

export default function Overview() {
  const overview = useOverview();
  const series = useTimeseries(24, 60);
  const requests = useRequests(8);

  if (overview.isLoading) return <Spinner />;
  if (overview.error) return <ErrorBox error={overview.error} />;
  if (!overview.data) return null;

  const data = overview.data;
  const summary = data.summary;
  const chart = (series.data ?? []).map((point) => ({
    ...point,
    label: new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(
      new Date(point.bucket),
    ),
  }));

  return (
    <div>
      <PageHeader
        title="Обзор"
        subtitle="Состояние шлюза и активность за последние 24 часа"
        action={<Badge status={data.service.status}>{data.service.status === "ok" ? "Работает" : data.service.status}</Badge>}
      />

      {data.service.mock ? (
        <div
          className="mb-5 rounded-xl border px-4 py-3 text-sm"
          style={{
            borderColor: "var(--warn)",
            color: "var(--warn)",
            background: "color-mix(in srgb, var(--warn) 8%, transparent)",
          }}
        >
          Активен локальный mock-провайдер. Запросы не уходят в Google; модель zv67-mock не является Google AI Mode.
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Запросов" value={summary.requests} hint={`за ${summary.period_hours} ч`} />
        <Stat
          label="Успешных"
          value={percent(summary.success_rate)}
          tone={summary.success_rate !== null && summary.success_rate < 0.9 ? "warn" : "ok"}
          hint={`${summary.successes} из ${summary.successes + summary.errors}`}
        />
        <Stat label="Средняя задержка" value={ms(summary.avg_latency_ms)} hint={`p95 ${ms(summary.p95_latency_ms)}`} />
        <Stat
          label="Аккаунты"
          value={`${data.accounts.enabled} / ${data.accounts.total}`}
          hint="включено из всего"
        />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Запросы по часам</h2>
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              UTC
            </span>
          </div>
          {chart.length === 0 ? (
            <Empty>Пока нет запросов. Отправьте тестовый запрос на /v1/chat/completions.</Empty>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chart}>
                  <defs>
                    <linearGradient id="requests" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6ea8fe" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#6ea8fe" stopOpacity={0} />
                    </linearGradient>
                  </defs>
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
                  <Area type="monotone" dataKey="requests" name="Запросы" stroke="#6ea8fe" fill="url(#requests)" />
                  <Area type="monotone" dataKey="errors" name="Ошибки" stroke="#f87171" fill="transparent" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold">Последние запросы</h2>
          {requests.data?.length ? (
            <div className="space-y-2">
              {requests.data.map((row) => (
                <div key={row.id} className="flex items-center justify-between gap-2 text-xs">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{row.model_id}</div>
                    <div style={{ color: "var(--muted)" }}>{formatDate(row.created_at)}</div>
                  </div>
                  <Badge status={row.status} />
                </div>
              ))}
            </div>
          ) : (
            <Empty>Журнал пуст</Empty>
          )}
        </Card>
      </div>

      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Сервис</h2>
          <dl className="space-y-2 text-sm">
            <Row label="Провайдер" value={data.service.provider} />
            <Row label="Версия" value={data.service.version} />
            <Row label="Маршрутизация" value={data.routing_strategy} />
            <Row label="Статус провайдера" value={data.service.provider_status} />
          </dl>
        </Card>
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Распределение</h2>
          {Object.keys(summary.by_model).length === 0 ? (
            <Empty>Нет данных</Empty>
          ) : (
            <div className="space-y-2 text-sm">
              {Object.entries(summary.by_model).map(([model, count]) => (
                <div key={model} className="flex justify-between">
                  <span>{model}</span>
                  <span style={{ color: "var(--muted)" }}>{count}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt style={{ color: "var(--muted)" }}>{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}


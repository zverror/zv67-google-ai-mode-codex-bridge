import { useState } from "react";
import { useRequests, useSessions } from "../api/hooks";
import {
  Badge,
  Card,
  Empty,
  ErrorBox,
  PageHeader,
  Spinner,
  formatDate,
  ms,
} from "../components/ui";

export default function Logs() {
  const requests = useRequests(200);
  const sessions = useSessions();
  const [filter, setFilter] = useState("ALL");

  if (requests.isLoading) return <Spinner />;
  if (requests.error) return <ErrorBox error={requests.error} />;

  const rows = (requests.data ?? []).filter(
    (row) => filter === "ALL" || row.status === filter,
  );

  return (
    <div>
      <PageHeader
        title="Журнал"
        subtitle="Метаданные запросов и локальные сессии. Содержимое промптов не пишется в журнал."
        action={
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="rounded-xl border px-3 py-2 text-sm"
            style={{ background: "var(--panel-2)", borderColor: "var(--border)", color: "var(--fg)" }}
          >
            <option value="ALL">Все статусы</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="ERROR">ERROR</option>
            <option value="STARTED">STARTED</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>
        }
      />

      <Card>
        {rows.length === 0 ? (
          <Empty>Записей нет</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs" style={{ color: "var(--muted)" }}>
                <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                  <th className="py-2 pr-3 font-medium">Время</th>
                  <th className="py-2 pr-3 font-medium">Модель</th>
                  <th className="py-2 pr-3 font-medium">Аккаунт</th>
                  <th className="py-2 pr-3 font-medium">Статус</th>
                  <th className="py-2 pr-3 font-medium">HTTP</th>
                  <th className="py-2 pr-3 font-medium">Задержка</th>
                  <th className="py-2 pr-3 font-medium">Ошибка</th>
                  <th className="py-2 font-medium">Request ID</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                    <td className="whitespace-nowrap py-2 pr-3 text-xs">{formatDate(row.created_at)}</td>
                    <td className="py-2 pr-3">{row.model_id}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{row.account_id ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <Badge status={row.status} />
                    </td>
                    <td className="py-2 pr-3">{row.http_status ?? "—"}</td>
                    <td className="py-2 pr-3">{ms(row.latency_ms)}</td>
                    <td className="py-2 pr-3 text-xs" style={{ color: "var(--bad)" }}>
                      {row.error_code ?? "—"}
                    </td>
                    <td className="py-2 font-mono text-[11px]" style={{ color: "var(--muted)" }}>
                      {row.id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <h2 className="mb-3 mt-6 text-sm font-semibold">Сессии</h2>
      <Card>
        {!sessions.data?.length ? (
          <Empty>Сессий нет</Empty>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {sessions.data.map((session) => (
              <div
                key={session.id}
                className="rounded-xl border px-3 py-2 text-xs"
                style={{ borderColor: "var(--border)" }}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono">{session.id.slice(0, 18)}…</span>
                  <span style={{ color: "var(--muted)" }}>{session.turn_count} ходов</span>
                </div>
                <div className="mt-1" style={{ color: "var(--muted)" }}>
                  {session.account_id ?? "без аккаунта"} · обновлено {formatDate(session.updated_at)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}


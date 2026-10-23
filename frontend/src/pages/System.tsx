import { useState } from "react";
import { useAudit, useSystem } from "../api/hooks";
import {
  Card,
  Empty,
  ErrorBox,
  PageHeader,
  Spinner,
  formatDate,
} from "../components/ui";

export default function System() {
  const system = useSystem();
  const audit = useAudit();
  const [health, setHealth] = useState<string>("");

  async function checkHealth() {
    setHealth("Проверка…");
    try {
      const response = await fetch("/health");
      const body = await response.json();
      setHealth(JSON.stringify(body));
    } catch {
      setHealth("Ошибка проверки");
    }
  }

  if (system.isLoading) return <Spinner />;
  if (system.error) return <ErrorBox error={system.error} />;
  if (!system.data) return null;

  return (
    <div>
      <PageHeader
        title="Система"
        subtitle="Версии, пути и журнал административных действий"
        action={
          <button
            onClick={checkHealth}
            className="rounded-xl border px-3 py-2 text-sm"
            style={{ borderColor: "var(--border)" }}
          >
            Проверить /health
          </button>
        }
      />

      {health ? (
        <pre
          className="mb-5 overflow-x-auto rounded-xl border p-3 text-xs"
          style={{ borderColor: "var(--border)", background: "var(--panel-2)" }}
        >
          {health}
        </pre>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold">Компоненты</h2>
          <dl className="space-y-2 text-sm">
            <Row label="Версия ZV67" value={system.data.version} />
            <Row label="Python" value={system.data.python} />
            <Row label="Платформа" value={system.data.platform} />
            <Row label="Провайдер" value={system.data.provider} />
            <Row label="Mock" value={system.data.mock ? "да" : "нет"} />
            <Row label="Хранилище ключа" value={system.data.master_key_store} />
            <Row label="Маршрутизация" value={system.data.routing_strategy} />
          </dl>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold">Локальные пути</h2>
          <dl className="space-y-2 text-sm">
            <Row label="База" value={system.data.database_path} mono />
            <Row label="Данные" value={system.data.data_dir} mono />
          </dl>
          <p className="mt-4 text-xs" style={{ color: "var(--muted)" }}>
            Cookies и содержимое диалогов хранятся в зашифрованном виде. В режиме keychain мастер-ключ
            находится в macOS Keychain; файловый режим использует файл с правами 0600.
          </p>
        </Card>
      </div>

      <h2 className="mb-3 mt-6 text-sm font-semibold">Административный журнал</h2>
      <Card>
        {audit.isLoading ? (
          <Spinner />
        ) : !audit.data?.length ? (
          <Empty>Записей нет</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs" style={{ color: "var(--muted)" }}>
                <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                  <th className="py-2 pr-3 font-medium">Время</th>
                  <th className="py-2 pr-3 font-medium">Действие</th>
                  <th className="py-2 pr-3 font-medium">Объект</th>
                  <th className="py-2 font-medium">Детали</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.map((entry) => (
                  <tr key={entry.id} className="border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                    <td className="whitespace-nowrap py-2 pr-3 text-xs">{formatDate(entry.created_at)}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{entry.action}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{entry.target ?? "—"}</td>
                    <td className="py-2 text-xs" style={{ color: "var(--muted)" }}>
                      {entry.detail ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <dt style={{ color: "var(--muted)" }}>{label}</dt>
      <dd className={`text-right ${mono ? "break-all font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}


import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, setCsrf } from "../api/client";
import { useSettings } from "../api/hooks";
import {
  Button,
  Card,
  ErrorBox,
  Field,
  PageHeader,
  Spinner,
  inputClass,
  inputStyle,
} from "../components/ui";

const STRATEGIES = [
  { value: "round_robin", label: "Round-robin" },
  { value: "weighted_round_robin", label: "Weighted round-robin" },
  { value: "least_busy", label: "Least-busy" },
  { value: "manual", label: "Только ручной выбор" },
];

export default function Settings() {
  const queryClient = useQueryClient();
  const settings = useSettings();
  const [strategy, setStrategy] = useState("round_robin");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  useEffect(() => {
    if (settings.data) setStrategy(settings.data.routing_strategy);
  }, [settings.data]);

  const saveRouting = useMutation({
    mutationFn: () =>
      api("/settings", {
        method: "PUT",
        body: JSON.stringify({ routing_strategy: strategy }),
      }),
    onSuccess: async () => {
      setMessage("Стратегия сохранена");
      setError("");
      await queryClient.invalidateQueries();
    },
    onError: (cause) => setError(cause.message),
  });

  const changePassword = useMutation({
    mutationFn: () =>
      api("/auth/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      }),
    onSuccess: () => {
      setMessage("Пароль изменён");
      setError("");
      setCurrent("");
      setNext("");
    },
    onError: (cause) => setError(cause.message),
  });

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setCsrf(null);
    window.location.reload();
  }

  function submitPassword(event: FormEvent) {
    event.preventDefault();
    changePassword.mutate();
  }

  if (settings.isLoading) return <Spinner />;
  if (settings.error) return <ErrorBox error={settings.error} />;
  if (!settings.data) return null;

  return (
    <div>
      <PageHeader title="Настройки" subtitle="Маршрутизация, сессии и защита панели" />

      {message ? (
        <div className="mb-4 text-sm" style={{ color: "var(--ok)" }}>
          {message}
        </div>
      ) : null}
      {error ? (
        <div className="mb-4">
          <ErrorBox error={new Error(error)} />
        </div>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-semibold">Маршрутизация</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            Диалог закрепляется за аккаунтом. Принудительная смена аккаунта внутри диалога не выполняется.
          </p>
          <div className="mt-4 space-y-3">
            <Field label="Стратегия для новых диалогов">
              <select
                className={inputClass}
                style={inputStyle()}
                value={strategy}
                onChange={(event) => setStrategy(event.target.value)}
              >
                {STRATEGIES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </Field>
            <Button onClick={() => saveRouting.mutate()} disabled={saveRouting.isPending}>
              {saveRouting.isPending ? "Сохранение…" : "Сохранить"}
            </Button>
          </div>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold">Параметры сервиса</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <Row label="Адрес" value={`${settings.data.host}:${settings.data.port}`} />
            <Row label="TTL сессии" value={`${settings.data.session_ttl_hours} ч`} />
            <Row label="Лимит сообщений" value={String(settings.data.max_messages)} />
            <Row label="Лимит размера сообщения" value={`${settings.data.max_message_chars} символов`} />
            <Row
              label="API key"
              value={settings.data.api_key_configured ? "настроен" : "не задан (только localhost)"}
            />
          </dl>
          <p className="mt-4 text-xs" style={{ color: "var(--muted)" }}>
            API key задаётся переменной ZV67_API_KEY при запуске сервиса.
          </p>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold">Пароль администратора</h2>
          <form className="mt-3 space-y-3" onSubmit={submitPassword}>
            <Field label="Текущий пароль">
              <input
                type="password"
                className={inputClass}
                style={inputStyle()}
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
                required
              />
            </Field>
            <Field label="Новый пароль" hint="Не короче 12 символов">
              <input
                type="password"
                className={inputClass}
                style={inputStyle()}
                value={next}
                onChange={(event) => setNext(event.target.value)}
                required
              />
            </Field>
            <Button type="submit" disabled={changePassword.isPending}>
              Изменить пароль
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold">Сессия</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            Cookie HttpOnly, SameSite=Strict. Изменяющие запросы защищены CSRF-токеном.
          </p>
          <Button variant="ghost" onClick={logout} className="mt-4">
            Выйти из панели
          </Button>
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


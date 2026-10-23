import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Account } from "../api/client";
import { useAccounts } from "../api/hooks";
import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorBox,
  Field,
  PageHeader,
  Spinner,
  formatDate,
  inputClass,
  inputStyle,
  ms,
} from "../components/ui";

const STATUS_LABEL: Record<string, string> = {
  ACTIVE: "Активен",
  DISABLED: "Отключён",
  UNAUTHORIZED: "Нет авторизации",
  DEGRADED: "Деградация",
  COOLDOWN: "Пауза",
  UNKNOWN: "Неизвестен",
};

export default function Accounts() {
  const queryClient = useQueryClient();
  const accounts = useAccounts();
  const [name, setName] = useState("");
  const [weight, setWeight] = useState(100);
  const [concurrency, setConcurrency] = useState(1);
  const [subscription, setSubscription] = useState("unknown");
  const [credentialAccount, setCredentialAccount] = useState<Account | null>(null);
  const [credentialText, setCredentialText] = useState("");
  const [credentialError, setCredentialError] = useState("");
  const [actionError, setActionError] = useState("");

  const invalidate = () => queryClient.invalidateQueries();

  const create = useMutation({
    mutationFn: () =>
      api<Account>("/accounts", {
        method: "POST",
        body: JSON.stringify({
          display_name: name,
          routing_weight: weight,
          concurrency_limit: concurrency,
          subscription_status: subscription,
        }),
      }),
    onSuccess: async () => {
      setName("");
      setActionError("");
      await invalidate();
    },
    onError: (error) => setActionError(error.message),
  });

  const toggle = useMutation({
    mutationFn: (account: Account) =>
      api(`/accounts/${account.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !account.enabled }),
      }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error.message),
  });

  const check = useMutation({
    mutationFn: (account: Account) =>
      api(`/accounts/${account.id}/check`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error.message),
  });

  const remove = useMutation({
    mutationFn: (account: Account) =>
      api(`/accounts/${account.id}`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (error) => setActionError(error.message),
  });

  const credentials = useMutation({
    mutationFn: (payload: { account: Account; body: string }) =>
      api(`/accounts/${payload.account.id}/credentials`, {
        method: "PUT",
        body: JSON.stringify({ credentials_text: payload.body }),
      }),
    onSuccess: async () => {
      setCredentialAccount(null);
      setCredentialText("");
      setCredentialError("");
      await invalidate();
    },
    onError: (error) => setCredentialError(error.message),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate();
  }

  function saveCredentials() {
    if (!credentialAccount) return;
    setCredentialError("");
    if (!credentialText.trim()) {
      setCredentialError("Вставьте cookies");
      return;
    }
    credentials.mutate({ account: credentialAccount, body: credentialText });
  }

  function confirmRemove(account: Account) {
    if (
      window.confirm(
        `Удалить аккаунт "${account.display_name}"? Вместе с ним будут удалены его credentials, сессии и история.`,
      )
    ) {
      remove.mutate(account);
    }
  }

  if (accounts.isLoading) return <Spinner />;
  if (accounts.error) return <ErrorBox error={accounts.error} />;

  return (
    <div>
      <PageHeader
        title="Аккаунты"
        subtitle="Изолированные профили, лимиты параллельности и распределение запросов"
      />

      {actionError ? (
        <div className="mb-4">
          <ErrorBox error={new Error(actionError)} />
        </div>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          {!accounts.data?.length ? (
            <Empty>Аккаунтов пока нет. Добавьте первый профиль справа.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs" style={{ color: "var(--muted)" }}>
                  <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                    <th className="py-2 pr-3 font-medium">Аккаунт</th>
                    <th className="py-2 pr-3 font-medium">Нагрузка</th>
                    <th className="py-2 pr-3 font-medium">Вес</th>
                    <th className="py-2 pr-3 font-medium">Запросы</th>
                    <th className="py-2 pr-3 font-medium">Последний успех</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {accounts.data.map((account) => (
                    <tr key={account.id} className="border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                      <td className="py-3 pr-3">
                        <div className="font-medium">{account.display_name}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5">
                          <Badge status={account.connection_status}>
                            {STATUS_LABEL[account.connection_status] ?? account.connection_status}
                          </Badge>
                          {account.has_credentials ? <Badge status="VERIFIED">credentials</Badge> : null}
                          {account.in_cooldown ? <Badge status="COOLDOWN">cooldown</Badge> : null}
                        </div>
                        {account.last_error ? (
                          <div className="mt-1 max-w-[280px] truncate text-xs" style={{ color: "var(--bad)" }}>
                            {account.last_error}
                          </div>
                        ) : null}
                      </td>
                      <td className="py-3 pr-3">
                        {account.active_requests} / {account.concurrency_limit}
                      </td>
                      <td className="py-3 pr-3">{account.routing_weight}</td>
                      <td className="py-3 pr-3">
                        <div>{account.statistics.requests}</div>
                        <div className="text-xs" style={{ color: "var(--muted)" }}>
                          {ms(account.statistics.avg_latency_ms)}
                        </div>
                      </td>
                      <td className="py-3 pr-3 text-xs">{formatDate(account.last_success_at)}</td>
                      <td className="py-3">
                        <div className="flex flex-wrap justify-end gap-1.5">
                          <Button variant="ghost" onClick={() => toggle.mutate(account)}>
                            {account.enabled ? "Отключить" : "Включить"}
                          </Button>
                          <Button variant="ghost" onClick={() => check.mutate(account)}>
                            Проверить
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => {
                              setCredentialAccount(account);
                              setCredentialText("");
                              setCredentialError("");
                            }}
                          >
                            Credentials
                          </Button>
                          <Button variant="danger" onClick={() => confirmRemove(account)}>
                            Удалить
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-5">
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Новый аккаунт</h2>
            <form className="space-y-3" onSubmit={submit}>
              <Field label="Название">
                <input
                  className={inputClass}
                  style={inputStyle()}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Google — основной"
                  required
                />
              </Field>
              <Field label="Подписка" hint="Показывается как задано; автоматически не определяется">
                <select
                  className={inputClass}
                  style={inputStyle()}
                  value={subscription}
                  onChange={(event) => setSubscription(event.target.value)}
                >
                  <option value="unknown">Неизвестен</option>
                  <option value="ai_pro">Google AI Pro</option>
                  <option value="ai_ultra">Google AI Ultra</option>
                </select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Вес">
                  <input
                    type="number"
                    min={1}
                    className={inputClass}
                    style={inputStyle()}
                    value={weight}
                    onChange={(event) => setWeight(Number(event.target.value))}
                  />
                </Field>
                <Field label="Параллельно">
                  <input
                    type="number"
                    min={1}
                    className={inputClass}
                    style={inputStyle()}
                    value={concurrency}
                    onChange={(event) => setConcurrency(Number(event.target.value))}
                  />
                </Field>
              </div>
              <Button type="submit" disabled={create.isPending} className="w-full">
                {create.isPending ? "Создание…" : "Добавить аккаунт"}
              </Button>
            </form>
          </Card>

          {credentialAccount ? (
            <Card>
              <h2 className="mb-1 text-sm font-semibold">Credentials: {credentialAccount.display_name}</h2>
              <p className="mb-3 text-xs" style={{ color: "var(--muted)" }}>
                Поддерживается JSON из Cookie-Editor, файл Netscape и строка name=value; name2=value2.
                Данные шифруются мастер-ключом. Не вставляйте cookies в логи или Git.
              </p>
              <textarea
                className={`${inputClass} h-40 font-mono text-xs`}
                style={inputStyle()}
                value={credentialText}
                onChange={(event) => setCredentialText(event.target.value)}
                placeholder='[{"name":"__Secure-1PSID","value":"..."}] или .google.com  TRUE  /  TRUE  1824327060  __Secure-1PSID  ...'
              />
              {credentialError ? (
                <div className="mt-2 text-xs" style={{ color: "var(--bad)" }}>
                  {credentialError}
                </div>
              ) : null}
              <div className="mt-3 flex gap-2">
                <Button onClick={saveCredentials} disabled={credentials.isPending}>
                  {credentials.isPending ? "Сохранение…" : "Сохранить"}
                </Button>
                <Button variant="ghost" onClick={() => setCredentialAccount(null)}>
                  Отмена
                </Button>
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}


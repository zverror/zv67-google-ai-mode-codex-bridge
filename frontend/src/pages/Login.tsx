import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setCsrf, type AuthStatus } from "../api/client";
import { Button, Card, Field, inputClass, inputStyle } from "../components/ui";

export default function Login({ status }: { status?: AuthStatus }) {
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const setup = !status?.configured;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (setup && password !== confirm) {
      setError("Пароли не совпадают");
      return;
    }
    setBusy(true);
    try {
      const response = await api<{ csrf_token: string }>(
        setup ? "/auth/setup" : "/auth/login",
        { method: "POST", body: JSON.stringify({ password }) },
      );
      setCsrf(response.csrf_token);
      await queryClient.invalidateQueries({ queryKey: ["auth"] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="text-3xl font-semibold tracking-tight">ZV67</div>
          <div className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            Google AI Mode Agent Gateway
          </div>
        </div>
        <Card>
          <h1 className="text-xl font-semibold">
            {setup ? "Первый запуск" : "Вход в панель"}
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {setup
              ? "Задайте пароль администратора. Он хранится только в виде scrypt-хеша."
              : "Введите пароль администратора."}
          </p>
          <form className="mt-5 space-y-4" onSubmit={submit}>
            <Field label="Пароль" hint={setup ? "Не короче 12 символов" : undefined}>
              <input
                type="password"
                className={inputClass}
                style={inputStyle()}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoFocus
                required
              />
            </Field>
            {setup ? (
              <Field label="Повторите пароль">
                <input
                  type="password"
                  className={inputClass}
                  style={inputStyle()}
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  required
                />
              </Field>
            ) : null}
            {error ? (
              <div className="text-sm" style={{ color: "var(--bad)" }}>
                {error}
              </div>
            ) : null}
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Проверка…" : setup ? "Задать пароль и войти" : "Войти"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-xs" style={{ color: "var(--muted)" }}>
          Сервер слушает только 127.0.0.1
        </p>
      </div>
    </div>
  );
}


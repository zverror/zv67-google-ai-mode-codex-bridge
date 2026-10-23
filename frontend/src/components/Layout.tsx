import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, setCsrf } from "../api/client";

const NAV = [
  { to: "/", label: "Обзор", icon: "M3 12h7V3H3v9Zm11 9h7V12h-7v9ZM3 21h7v-6H3v6Zm11-12h7V3h-7v6Z" },
  { to: "/accounts", label: "Аккаунты", icon: "M16 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM8 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8 8v-2a4 4 0 0 0-4-4H4a4 4 0 0 0-4 4v2m24 0v-2a4 4 0 0 0-3-3.87" },
  { to: "/models", label: "Модели", icon: "M12 2 3 7v10l9 5 9-5V7l-9-5Zm0 5 5 2.5v5L12 17l-5-2.5v-5L12 7Z" },
  { to: "/usage", label: "Статистика", icon: "M4 20V10m6 10V4m6 16v-7m4 7V8" },
  { to: "/logs", label: "Журнал", icon: "M5 4h14v16H5zM8 8h8M8 12h8M8 16h5" },
  { to: "/settings", label: "Настройки", icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8-3a8 8 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a8 8 0 0 0-1.7-1L15.4 3h-4l-.4 2.6a8 8 0 0 0-1.7 1l-2.4-1-2 3.4L7.1 11a8 8 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.4 2.6h4l.4-2.6a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6c.06-.33.1-.66.1-1Z" },
  { to: "/system", label: "Система", icon: "M4 5h16v10H4zM8 19h8M12 15v4" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem("zv67_theme");
    return stored ? stored === "dark" : true;
  });
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("zv67_theme", next ? "dark" : "light");
  }

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    setCsrf(null);
    queryClient.clear();
    navigate("/");
  }

  return (
    <div className="min-h-screen md:flex">
      <aside
        className="md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 border-b md:border-b-0 md:border-r"
        style={{ background: "var(--panel)", borderColor: "var(--border)" }}
      >
        <div className="flex items-center justify-between px-5 py-4 md:block">
          <div>
            <div className="text-lg font-semibold tracking-tight">ZV67</div>
            <div className="text-[11px]" style={{ color: "var(--muted)" }}>
              Google AI Mode Gateway
            </div>
          </div>
          <button
            onClick={toggleTheme}
            className="rounded-lg border px-2 py-1 text-xs md:hidden"
            style={{ borderColor: "var(--border)" }}
          >
            {dark ? "Светлая" : "Тёмная"}
          </button>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-3 md:pb-4">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                "flex shrink-0 items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition " +
                (isActive ? "font-medium" : "")
              }
              style={({ isActive }) => ({
                background: isActive ? "var(--accent-soft)" : "transparent",
                color: isActive ? "var(--accent)" : "var(--muted)",
              })}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d={item.icon} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden px-5 pb-5 md:block">
          <button
            onClick={toggleTheme}
            className="mb-2 w-full rounded-xl border px-3 py-2 text-left text-xs"
            style={{ borderColor: "var(--border)", color: "var(--muted)" }}
          >
            {dark ? "Светлая тема" : "Тёмная тема"}
          </button>
          <button
            onClick={logout}
            className="w-full rounded-xl border px-3 py-2 text-left text-xs"
            style={{ borderColor: "var(--border)", color: "var(--muted)" }}
          >
            Выйти
          </button>
        </div>
      </aside>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8">{children}</main>
    </div>
  );
}


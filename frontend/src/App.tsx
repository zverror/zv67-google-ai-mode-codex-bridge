import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Route, Routes } from "react-router-dom";
import { useAuthStatus } from "./api/hooks";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Accounts from "./pages/Accounts";
import Models from "./pages/Models";
import Usage from "./pages/Usage";
import Logs from "./pages/Logs";
import Settings from "./pages/Settings";
import System from "./pages/System";
import { Spinner } from "./components/ui";

export default function App() {
  const queryClient = useQueryClient();
  const auth = useAuthStatus();

  useEffect(() => {
    const stored = localStorage.getItem("zv67_theme");
    document.documentElement.classList.toggle("dark", stored ? stored === "dark" : true);
  }, []);

  useEffect(() => {
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: ["auth"] });
    };
    window.addEventListener("zv67-unauthorized", handler);
    return () => window.removeEventListener("zv67-unauthorized", handler);
  }, [queryClient]);

  if (auth.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner />
      </div>
    );
  }

  if (!auth.data?.authenticated) {
    return <Login status={auth.data} />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/models" element={<Models />} />
        <Route path="/usage" element={<Usage />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/system" element={<System />} />
      </Routes>
    </Layout>
  );
}


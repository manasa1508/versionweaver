import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { LoadingState } from "./components/Common";
import { Layout } from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import { ApiError } from "./lib/api";

const AuditPage = lazy(() => import("./pages/AuditPage").then((module) => ({ default: module.AuditPage })));
const ChangeDetailPage = lazy(() => import("./pages/ChangeDetailPage").then((module) => ({ default: module.ChangeDetailPage })));
const ChangesPage = lazy(() => import("./pages/ChangesPage").then((module) => ({ default: module.ChangesPage })));
const JobsPage = lazy(() => import("./pages/JobsPage").then((module) => ({ default: module.JobsPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })));
const OverviewPage = lazy(() => import("./pages/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const ProjectsPage = lazy(() => import("./pages/ProjectsPage").then((module) => ({ default: module.ProjectsPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: true,
      retry: (count, error) => count < 2 && (!(error instanceof ApiError) || error.status === 0 || error.status >= 500)
    },
    mutations: { retry: false }
  }
});

function ProtectedShell() {
  const auth = useAuth();
  return auth.authenticated ? <Layout /> : <Navigate to="/connect" replace />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="route-loading"><LoadingState /></div>}>
        <Routes>
          <Route path="/connect" element={<LoginPage />} />
          <Route element={<ProtectedShell />}>
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/changes" element={<ChangesPage />} />
            <Route path="/changes/:changeId" element={<ChangeDetailPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </Suspense>
    </QueryClientProvider>
  );
}

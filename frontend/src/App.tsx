import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { AppShell } from "./components/AppShell";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { Dashboard } from "./pages/Dashboard";
import { Intake } from "./pages/Intake";
import { Login } from "./pages/Login";
import { QuickBrief } from "./pages/QuickBrief";
import { Worklist } from "./pages/Worklist";

function Protected({ children }: { children: any }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-full grid place-items-center text-muted text-sm">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><AppShell /></Protected>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/intake" element={<Intake />} />
        <Route path="/cases" element={<Worklist title="All cases" />} />
        <Route path="/cases/:id" element={<CaseDetailPage />} />
        <Route path="/worklist" element={<Worklist mine title="My worklist" />} />
        <Route path="/quick-brief" element={<QuickBrief />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

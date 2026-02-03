import { Routes, Route, Navigate } from "react-router-dom";
import { useStore } from "./store";
import { InstallPrompt } from "./components/InstallPrompt";
import Lobby from "./pages/Lobby";
import Table from "./pages/Table";
import Login from "./pages/Login";

// Spectator routes - no auth required for viewing
// Auth is only for agents connecting via SDK

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useStore((state) => state.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <div className="min-h-screen bg-slate-900">
      <Routes>
        {/* Public spectator routes - humans watch AI agents play */}
        <Route path="/" element={<Lobby />} />
        <Route path="/watch/:tableId" element={<Table />} />
        <Route path="/spectator" element={<Navigate to="/" replace />} />

        {/* Code Golf spectator view */}
        <Route path="/codegolf" element={<Lobby />} />
        <Route path="/codegolf/:challengeId" element={<Lobby />} />

        {/* Tournaments spectator view */}
        <Route path="/tournaments" element={<Lobby />} />
        <Route path="/tournaments/:tournamentId" element={<Lobby />} />

        {/* Analytics - public view of platform stats */}
        <Route path="/analytics" element={<Lobby />} />

        {/* Agent auth - for SDK connections (not human players) */}
        <Route path="/login" element={<Login />} />
        <Route
          path="/table/:tableId"
          element={
            <ProtectedRoute>
              <Table />
            </ProtectedRoute>
          }
        />

        {/* Admin panel - separate auth */}
        <Route path="/admin/*" element={<Lobby />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* PWA install prompt */}
      <InstallPrompt />
    </div>
  );
}

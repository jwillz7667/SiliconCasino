import { Routes, Route, Navigate } from "react-router-dom";
import { useStore } from "./store";
import Lobby from "./pages/Lobby";
import Table from "./pages/Table";
import Login from "./pages/Login";

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
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Lobby />
            </ProtectedRoute>
          }
        />
        <Route
          path="/table/:tableId"
          element={
            <ProtectedRoute>
              <Table />
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

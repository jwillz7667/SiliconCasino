import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useStore } from "../store";

export default function Login() {
  const navigate = useNavigate();
  const { setToken, setAgentId, setBalance } = useStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [apiKey, setApiKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [registeredKey, setRegisteredKey] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { access_token } = await api.getToken(apiKey);
      setToken(access_token);

      const me = await api.getMe(access_token);
      setAgentId(me.id);

      const { balance } = await api.getBalance(access_token);
      setBalance(balance);

      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await api.register(displayName);
      setRegisteredKey(data.api_key);
      setApiKey(data.api_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="bg-slate-800/80 backdrop-blur-sm p-8 rounded-xl shadow-2xl w-full max-w-md border border-slate-700">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-casino-gold mb-2">
            Silicon Casino
          </h1>
          <p className="text-slate-400">AI Poker Platform</p>
        </div>

        <div className="flex mb-6">
          <button
            onClick={() => setMode("login")}
            className={`flex-1 py-2 text-sm font-medium rounded-l-lg transition ${
              mode === "login"
                ? "bg-casino-gold text-black"
                : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
          >
            Login
          </button>
          <button
            onClick={() => setMode("register")}
            className={`flex-1 py-2 text-sm font-medium rounded-r-lg transition ${
              mode === "register"
                ? "bg-casino-gold text-black"
                : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
          >
            Register
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-200 text-sm">
            {error}
          </div>
        )}

        {registeredKey && (
          <div className="mb-4 p-3 bg-green-900/50 border border-green-700 rounded-lg text-green-200 text-sm">
            <p className="font-semibold mb-1">Registration successful!</p>
            <p className="text-xs mb-2">Save this API key - it cannot be retrieved later:</p>
            <code className="block p-2 bg-slate-900 rounded text-xs break-all">
              {registeredKey}
            </code>
          </div>
        )}

        {mode === "login" ? (
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                API Key
              </label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-casino-gold"
                placeholder="sk_..."
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-casino-gold text-black font-semibold rounded-lg hover:bg-yellow-500 transition disabled:opacity-50"
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-casino-gold"
                placeholder="Your agent name"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-casino-gold text-black font-semibold rounded-lg hover:bg-yellow-500 transition disabled:opacity-50"
            >
              {loading ? "Registering..." : "Register"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

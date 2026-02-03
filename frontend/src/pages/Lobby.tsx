import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useStore } from "../store";

interface TableInfo {
  id: string;
  name: string;
  small_blind: number;
  big_blind: number;
  min_buy_in: number;
  max_buy_in: number;
  max_players: number;
  player_count: number;
}

export default function Lobby() {
  const navigate = useNavigate();
  const { token, balance, setBalance, logout } = useStore();
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTable, setNewTable] = useState({
    name: "",
    small_blind: 5,
    big_blind: 10,
    min_buy_in: 100,
    max_buy_in: 1000,
    max_players: 6,
  });

  useEffect(() => {
    if (!token) return;

    const fetchData = async () => {
      try {
        const [tablesData, balanceData] = await Promise.all([
          api.listTables(token),
          api.getBalance(token),
        ]);
        setTables(tablesData.tables);
        setBalance(balanceData.balance);
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [token, setBalance]);

  const handleCreateTable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    try {
      const table = await api.createTable(token, newTable);
      setTables([...tables, { ...table, player_count: 0 }]);
      setShowCreateModal(false);
      navigate(`/table/${table.id}`);
    } catch (err) {
      console.error("Failed to create table:", err);
    }
  };

  const handleCreditChips = async () => {
    if (!token) return;
    try {
      const result = await api.creditChips(token, 10000);
      setBalance(result.new_balance);
    } catch (err) {
      console.error("Failed to credit chips:", err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl text-slate-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
      <header className="max-w-6xl mx-auto mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-casino-gold">Silicon Casino</h1>
          <p className="text-slate-400">AI Poker Platform</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="bg-slate-800 px-4 py-2 rounded-lg">
            <span className="text-slate-400 text-sm">Balance:</span>
            <span className="ml-2 text-casino-gold font-bold">
              {balance.toLocaleString()}
            </span>
          </div>
          <button
            onClick={handleCreditChips}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition text-sm"
          >
            +10,000 Chips
          </button>
          <button
            onClick={logout}
            className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition text-sm"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white">Poker Tables</h2>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-casino-gold text-black font-semibold rounded-lg hover:bg-yellow-500 transition"
          >
            Create Table
          </button>
        </div>

        {tables.length === 0 ? (
          <div className="bg-slate-800/50 rounded-xl p-12 text-center">
            <p className="text-slate-400 mb-4">No tables available</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-6 py-3 bg-casino-gold text-black font-semibold rounded-lg hover:bg-yellow-500 transition"
            >
              Create First Table
            </button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {tables.map((table) => (
              <div
                key={table.id}
                className="bg-slate-800/80 rounded-xl p-6 border border-slate-700 hover:border-casino-gold/50 transition cursor-pointer"
                onClick={() => navigate(`/table/${table.id}`)}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">{table.name}</h3>
                  <span className="text-sm text-slate-400">
                    {table.player_count}/{table.max_players}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Blinds:</span>
                    <span className="text-white">
                      {table.small_blind}/{table.big_blind}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Buy-in:</span>
                    <span className="text-white">
                      {table.min_buy_in} - {table.max_buy_in}
                    </span>
                  </div>
                </div>
                <button className="mt-4 w-full py-2 bg-felt text-white rounded-lg hover:bg-felt-light transition">
                  Join Table
                </button>
              </div>
            ))}
          </div>
        )}
      </main>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-semibold text-white mb-4">Create Table</h2>
            <form onSubmit={handleCreateTable}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Name</label>
                  <input
                    type="text"
                    value={newTable.name}
                    onChange={(e) =>
                      setNewTable({ ...newTable, name: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">
                      Small Blind
                    </label>
                    <input
                      type="number"
                      value={newTable.small_blind}
                      onChange={(e) =>
                        setNewTable({
                          ...newTable,
                          small_blind: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">
                      Big Blind
                    </label>
                    <input
                      type="number"
                      value={newTable.big_blind}
                      onChange={(e) =>
                        setNewTable({
                          ...newTable,
                          big_blind: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                      required
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">
                      Min Buy-in
                    </label>
                    <input
                      type="number"
                      value={newTable.min_buy_in}
                      onChange={(e) =>
                        setNewTable({
                          ...newTable,
                          min_buy_in: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">
                      Max Buy-in
                    </label>
                    <input
                      type="number"
                      value={newTable.max_buy_in}
                      onChange={(e) =>
                        setNewTable({
                          ...newTable,
                          max_buy_in: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-slate-400 mb-1">
                    Max Players
                  </label>
                  <select
                    value={newTable.max_players}
                    onChange={(e) =>
                      setNewTable({
                        ...newTable,
                        max_players: parseInt(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                  >
                    {[2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                      <option key={n} value={n}>
                        {n} players
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="mt-6 flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 bg-casino-gold text-black font-semibold rounded-lg hover:bg-yellow-500 transition"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

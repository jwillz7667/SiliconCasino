import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useStore } from "../store";
import PokerTable from "../components/PokerTable";
import ActionButtons from "../components/ActionButtons";

interface TableData {
  table: {
    table_id: string;
    name: string;
    small_blind: number;
    big_blind: number;
    button_position: number;
    seats: SeatData[];
  };
  hand: HandData | null;
  valid_actions: string[];
  is_your_turn: boolean;
}

interface SeatData {
  seat_number: number;
  agent_id: string | null;
  stack: number;
  status: string;
}

interface HandData {
  hand_id: string;
  phase: string;
  community_cards: string[];
  pot: number;
  current_bet: number;
  action_on: number;
  min_raise_to: number;
  your_cards?: string[];
  players: Record<
    string,
    {
      bet_this_round: number;
      is_folded: boolean;
      is_all_in: boolean;
      stack: number;
    }
  >;
}

export default function Table() {
  const { tableId } = useParams<{ tableId: string }>();
  const navigate = useNavigate();
  const { token, agentId, balance, setBalance } = useStore();

  const [tableData, setTableData] = useState<TableData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mySeat, setMySeat] = useState<number | null>(null);
  const [showJoinModal, setShowJoinModal] = useState(false);
  const [selectedSeat, setSelectedSeat] = useState<number | null>(null);
  const [buyIn, setBuyIn] = useState(500);

  const fetchTable = useCallback(async () => {
    if (!token || !tableId) return;
    try {
      const data = await api.getTable(token, tableId);
      setTableData(data);

      const seat = data.table.seats.find(
        (s: SeatData) => s.agent_id === agentId
      );
      setMySeat(seat ? seat.seat_number : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load table");
    } finally {
      setLoading(false);
    }
  }, [token, tableId, agentId]);

  useEffect(() => {
    fetchTable();
    const interval = setInterval(fetchTable, 1000);
    return () => clearInterval(interval);
  }, [fetchTable]);

  const handleJoinTable = async () => {
    if (!token || !tableId || selectedSeat === null) return;
    try {
      await api.joinTable(token, tableId, selectedSeat, buyIn);
      setShowJoinModal(false);
      setBalance(balance - buyIn);
      fetchTable();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to join table");
    }
  };

  const handleLeaveTable = async () => {
    if (!token || !tableId) return;
    try {
      const result = await api.leaveTable(token, tableId);
      setBalance(balance + result.chips_returned);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to leave table");
    }
  };

  const handleAction = async (action: string, amount?: number) => {
    if (!token || !tableId) return;
    try {
      await api.takeAction(token, tableId, action, amount || 0);
      fetchTable();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to take action");
    }
  };

  const handleSeatClick = (seatNumber: number) => {
    if (mySeat !== null) return;
    const seat = tableData?.table.seats.find((s) => s.seat_number === seatNumber);
    if (seat && !seat.agent_id) {
      setSelectedSeat(seatNumber);
      setShowJoinModal(true);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl text-slate-400">Loading...</div>
      </div>
    );
  }

  if (!tableData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl text-red-400">{error || "Table not found"}</div>
      </div>
    );
  }

  const currentBet = tableData.hand?.current_bet || 0;
  const minRaise = tableData.hand?.min_raise_to || tableData.table.big_blind * 2;
  const myStack =
    mySeat !== null
      ? tableData.hand?.players[mySeat]?.stack ??
        tableData.table.seats.find((s) => s.seat_number === mySeat)?.stack ??
        0
      : 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      <header className="max-w-6xl mx-auto mb-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="px-3 py-1 text-slate-400 hover:text-white transition"
          >
            ← Back
          </button>
          <h1 className="text-xl font-bold text-white">{tableData.table.name}</h1>
          <span className="text-sm text-slate-400">
            Blinds: {tableData.table.small_blind}/{tableData.table.big_blind}
          </span>
        </div>
        <div className="flex items-center gap-4">
          {mySeat !== null && (
            <button
              onClick={handleLeaveTable}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-500 transition text-sm"
            >
              Leave Table
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="max-w-6xl mx-auto mb-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-200 text-sm">
          {error}
          <button onClick={() => setError("")} className="ml-2 text-red-400">
            ×
          </button>
        </div>
      )}

      <main className="max-w-6xl mx-auto">
        <PokerTable
          seats={tableData.table.seats}
          buttonPosition={tableData.table.button_position}
          communityCards={tableData.hand?.community_cards || []}
          pot={tableData.hand?.pot || 0}
          phase={tableData.hand?.phase || "WAITING"}
          actionOn={tableData.hand?.action_on ?? -1}
          playerData={tableData.hand?.players || {}}
          myCards={tableData.hand?.your_cards || []}
          mySeat={mySeat}
          onSeatClick={handleSeatClick}
        />

        {mySeat !== null && tableData.is_your_turn && (
          <ActionButtons
            validActions={tableData.valid_actions}
            currentBet={currentBet}
            minRaise={minRaise}
            myStack={myStack}
            myBet={tableData.hand?.players[mySeat]?.bet_this_round || 0}
            onAction={handleAction}
          />
        )}

        {mySeat !== null && !tableData.is_your_turn && tableData.hand && (
          <div className="mt-4 text-center text-slate-400">
            Waiting for other players...
          </div>
        )}

        {mySeat === null && (
          <div className="mt-4 text-center text-slate-400">
            Click an empty seat to join the table
          </div>
        )}
      </main>

      {showJoinModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-sm">
            <h2 className="text-xl font-semibold text-white mb-4">
              Join Seat {selectedSeat}
            </h2>
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-1">Buy-in</label>
              <input
                type="range"
                min={tableData.table.small_blind * 20}
                max={Math.min(tableData.table.big_blind * 100, balance)}
                value={buyIn}
                onChange={(e) => setBuyIn(parseInt(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-sm text-slate-400 mt-1">
                <span>{tableData.table.small_blind * 20}</span>
                <span className="text-casino-gold font-bold">{buyIn}</span>
                <span>{Math.min(tableData.table.big_blind * 100, balance)}</span>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowJoinModal(false)}
                className="flex-1 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleJoinTable}
                className="flex-1 py-2 bg-casino-gold text-black font-semibold rounded-lg hover:bg-yellow-500 transition"
              >
                Join
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

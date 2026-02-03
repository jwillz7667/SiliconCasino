import { create } from "zustand";
import { persist } from "zustand/middleware";

interface GameState {
  table: TableState | null;
  hand: HandState | null;
  validActions: string[];
  isYourTurn: boolean;
}

interface TableState {
  table_id: string;
  name: string;
  small_blind: number;
  big_blind: number;
  button_position: number;
  seats: SeatState[];
}

interface SeatState {
  seat_number: number;
  agent_id: string | null;
  stack: number;
  status: string;
}

interface HandState {
  hand_id: string;
  phase: string;
  community_cards: string[];
  pot: number;
  current_bet: number;
  action_on: number;
  your_cards?: string[];
  players: Record<
    number,
    {
      bet_this_round: number;
      is_folded: boolean;
      is_all_in: boolean;
      stack: number;
    }
  >;
}

interface Store {
  token: string | null;
  agentId: string | null;
  balance: number;
  gameState: GameState | null;
  ws: WebSocket | null;

  setToken: (token: string | null) => void;
  setAgentId: (id: string | null) => void;
  setBalance: (balance: number) => void;
  setGameState: (state: GameState | null) => void;
  setWs: (ws: WebSocket | null) => void;
  logout: () => void;
}

export const useStore = create<Store>()(
  persist(
    (set) => ({
      token: null,
      agentId: null,
      balance: 0,
      gameState: null,
      ws: null,

      setToken: (token) => set({ token }),
      setAgentId: (agentId) => set({ agentId }),
      setBalance: (balance) => set({ balance }),
      setGameState: (gameState) => set({ gameState }),
      setWs: (ws) => set({ ws }),
      logout: () =>
        set({ token: null, agentId: null, balance: 0, gameState: null }),
    }),
    {
      name: "silicon-casino-storage",
      partialize: (state) => ({
        token: state.token,
        agentId: state.agentId,
      }),
    }
  )
);

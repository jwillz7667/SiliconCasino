import PlayerSeat from "./PlayerSeat";
import Card from "./Card";

interface SeatData {
  seat_number: number;
  agent_id: string | null;
  stack: number;
  status: string;
}

interface PlayerData {
  bet_this_round: number;
  is_folded: boolean;
  is_all_in: boolean;
  stack: number;
}

interface PokerTableProps {
  seats: SeatData[];
  buttonPosition: number;
  communityCards: string[];
  pot: number;
  phase: string;
  actionOn: number;
  playerData: Record<string, PlayerData>;
  myCards: string[];
  mySeat: number | null;
  onSeatClick: (seatNumber: number) => void;
}

const SEAT_POSITIONS: Record<number, { x: number; y: number }> = {
  0: { x: 50, y: 90 },
  1: { x: 15, y: 70 },
  2: { x: 15, y: 30 },
  3: { x: 50, y: 10 },
  4: { x: 85, y: 30 },
  5: { x: 85, y: 70 },
};

export default function PokerTable({
  seats,
  buttonPosition,
  communityCards,
  pot,
  phase,
  actionOn,
  playerData,
  myCards,
  mySeat,
  onSeatClick,
}: PokerTableProps) {
  return (
    <div className="relative w-full aspect-[2/1] max-w-4xl mx-auto">
      {/* Table felt */}
      <div className="absolute inset-[10%] bg-gradient-to-br from-felt to-felt-dark rounded-[50%] border-8 border-amber-900 shadow-2xl">
        {/* Inner rail */}
        <div className="absolute inset-4 rounded-[50%] border-2 border-felt-light/30" />

        {/* Center area */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {/* Phase indicator */}
          <div className="text-slate-300/60 text-sm mb-2">{phase}</div>

          {/* Community cards */}
          <div className="flex gap-2 mb-4">
            {communityCards.length > 0 ? (
              communityCards.map((card, i) => <Card key={i} card={card} />)
            ) : (
              <div className="text-slate-400/40 text-sm">
                {phase === "WAITING" ? "Waiting for players..." : ""}
              </div>
            )}
          </div>

          {/* Pot */}
          {pot > 0 && (
            <div className="bg-black/30 px-4 py-1 rounded-full">
              <span className="text-casino-gold font-bold">
                Pot: {pot.toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Seats */}
      {seats.map((seat) => {
        const pos = SEAT_POSITIONS[seat.seat_number] || { x: 50, y: 50 };
        const data = playerData[seat.seat_number.toString()];

        return (
          <div
            key={seat.seat_number}
            className="absolute transform -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
          >
            <PlayerSeat
              seat={seat}
              isButton={seat.seat_number === buttonPosition}
              isActive={seat.seat_number === actionOn}
              isFolded={data?.is_folded || false}
              isAllIn={data?.is_all_in || false}
              betAmount={data?.bet_this_round || 0}
              stack={data?.stack ?? seat.stack}
              cards={seat.seat_number === mySeat ? myCards : undefined}
              onClick={() => onSeatClick(seat.seat_number)}
            />
          </div>
        );
      })}
    </div>
  );
}

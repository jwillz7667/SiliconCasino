import Card from "./Card";

interface SeatData {
  seat_number: number;
  agent_id: string | null;
  stack: number;
  status: string;
}

interface PlayerSeatProps {
  seat: SeatData;
  isButton: boolean;
  isActive: boolean;
  isFolded: boolean;
  isAllIn: boolean;
  betAmount: number;
  stack: number;
  cards?: string[];
  onClick: () => void;
}

export default function PlayerSeat({
  seat,
  isButton,
  isActive,
  isFolded,
  isAllIn,
  betAmount,
  stack,
  cards,
  onClick,
}: PlayerSeatProps) {
  const isEmpty = !seat.agent_id;

  if (isEmpty) {
    return (
      <button
        onClick={onClick}
        className="w-24 h-16 bg-slate-800/50 border-2 border-dashed border-slate-600 rounded-lg hover:border-casino-gold hover:bg-slate-700/50 transition flex items-center justify-center"
      >
        <span className="text-slate-500 text-sm">Seat {seat.seat_number}</span>
      </button>
    );
  }

  return (
    <div className="relative">
      {/* Bet amount */}
      {betAmount > 0 && (
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-900 px-2 py-0.5 rounded text-sm text-casino-gold whitespace-nowrap">
          {betAmount}
        </div>
      )}

      {/* Player card */}
      <div
        className={`w-28 p-2 rounded-lg border-2 transition ${
          isActive
            ? "bg-slate-700 border-casino-gold shadow-lg shadow-casino-gold/20"
            : isFolded
            ? "bg-slate-800/50 border-slate-700 opacity-50"
            : "bg-slate-800 border-slate-600"
        }`}
      >
        {/* Name and stack */}
        <div className="text-center mb-1">
          <div className="text-xs text-slate-400 truncate">
            {seat.agent_id?.slice(0, 8)}...
          </div>
          <div className="text-sm font-bold text-white">
            {stack.toLocaleString()}
          </div>
        </div>

        {/* Cards */}
        {cards && cards.length > 0 && !isFolded && (
          <div className="flex justify-center gap-1">
            {cards.map((card, i) => (
              <Card key={i} card={card} size="small" />
            ))}
          </div>
        )}

        {/* Face-down cards indicator */}
        {!cards && !isFolded && seat.agent_id && (
          <div className="flex justify-center gap-1">
            <div className="w-6 h-8 bg-gradient-to-br from-blue-900 to-blue-950 rounded border border-blue-700" />
            <div className="w-6 h-8 bg-gradient-to-br from-blue-900 to-blue-950 rounded border border-blue-700" />
          </div>
        )}

        {/* Status badges */}
        <div className="flex justify-center gap-1 mt-1">
          {isAllIn && (
            <span className="text-xs bg-red-600 text-white px-1 rounded">
              ALL IN
            </span>
          )}
          {isFolded && (
            <span className="text-xs bg-slate-600 text-slate-300 px-1 rounded">
              FOLD
            </span>
          )}
        </div>
      </div>

      {/* Dealer button */}
      {isButton && (
        <div className="absolute -right-2 -top-2 w-6 h-6 bg-white rounded-full flex items-center justify-center text-xs font-bold text-black shadow-lg">
          D
        </div>
      )}
    </div>
  );
}

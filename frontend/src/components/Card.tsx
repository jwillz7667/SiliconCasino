interface CardProps {
  card: string;
  size?: "small" | "normal";
}

const SUIT_SYMBOLS: Record<string, string> = {
  h: "♥",
  d: "♦",
  c: "♣",
  s: "♠",
};

const SUIT_COLORS: Record<string, string> = {
  h: "text-red-500",
  d: "text-red-500",
  c: "text-gray-900",
  s: "text-gray-900",
};

export default function Card({ card, size = "normal" }: CardProps) {
  if (!card || card.length < 2) {
    return (
      <div
        className={`bg-gradient-to-br from-blue-900 to-blue-950 rounded border border-blue-700 ${
          size === "small" ? "w-6 h-8" : "w-10 h-14"
        }`}
      />
    );
  }

  const rank = card[0].toUpperCase();
  const suit = card[1].toLowerCase();
  const suitSymbol = SUIT_SYMBOLS[suit] || suit;
  const suitColor = SUIT_COLORS[suit] || "text-gray-900";

  return (
    <div
      className={`bg-gradient-to-br from-white to-gray-100 rounded shadow-md flex flex-col items-center justify-center font-bold ${suitColor} ${
        size === "small" ? "w-6 h-8 text-xs" : "w-10 h-14 text-sm"
      }`}
    >
      <span>{rank}</span>
      <span className={size === "small" ? "text-[10px]" : "text-xs"}>
        {suitSymbol}
      </span>
    </div>
  );
}

import { useState } from "react";

interface ActionButtonsProps {
  validActions: string[];
  currentBet: number;
  minRaise: number;
  myStack: number;
  myBet: number;
  onAction: (action: string, amount?: number) => void;
}

export default function ActionButtons({
  validActions,
  currentBet,
  minRaise,
  myStack,
  myBet,
  onAction,
}: ActionButtonsProps) {
  const [raiseAmount, setRaiseAmount] = useState(minRaise);
  const callAmount = Math.min(currentBet - myBet, myStack);

  const canFold = validActions.includes("FOLD");
  const canCheck = validActions.includes("CHECK");
  const canCall = validActions.includes("CALL");
  const canBet = validActions.includes("BET");
  const canRaise = validActions.includes("RAISE");
  const canAllIn = validActions.includes("ALL_IN");

  const handleRaise = () => {
    if (canBet) {
      onAction("bet", raiseAmount);
    } else if (canRaise) {
      onAction("raise", raiseAmount);
    }
  };

  return (
    <div className="mt-6 bg-slate-800/80 rounded-xl p-4 max-w-2xl mx-auto">
      <div className="flex items-center justify-center gap-3 flex-wrap">
        {canFold && (
          <button
            onClick={() => onAction("fold")}
            className="px-6 py-3 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-500 transition"
          >
            Fold
          </button>
        )}

        {canCheck && (
          <button
            onClick={() => onAction("check")}
            className="px-6 py-3 bg-slate-600 text-white font-semibold rounded-lg hover:bg-slate-500 transition"
          >
            Check
          </button>
        )}

        {canCall && (
          <button
            onClick={() => onAction("call")}
            className="px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-500 transition"
          >
            Call {callAmount}
          </button>
        )}

        {(canBet || canRaise) && (
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={minRaise}
              max={myStack + myBet}
              value={raiseAmount}
              onChange={(e) => setRaiseAmount(parseInt(e.target.value))}
              className="w-32"
            />
            <input
              type="number"
              value={raiseAmount}
              onChange={(e) => setRaiseAmount(parseInt(e.target.value) || minRaise)}
              min={minRaise}
              max={myStack + myBet}
              className="w-20 px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-center"
            />
            <button
              onClick={handleRaise}
              className="px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-500 transition"
            >
              {canBet ? "Bet" : "Raise"}
            </button>
          </div>
        )}

        {canAllIn && (
          <button
            onClick={() => onAction("all_in")}
            className="px-6 py-3 bg-purple-600 text-white font-semibold rounded-lg hover:bg-purple-500 transition"
          >
            All In ({myStack})
          </button>
        )}
      </div>

      <div className="mt-3 text-center text-sm text-slate-400">
        Your stack: {myStack.toLocaleString()} | Current bet: {currentBet} |
        Min raise: {minRaise}
      </div>
    </div>
  );
}

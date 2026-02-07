"use client";

interface MicFabProps {
  isActive: boolean;
  onClick: () => void;
}

export default function MicFab({ isActive, onClick }: MicFabProps) {
  return (
    <button className={`mic-fab ${isActive ? "active" : ""}`} onClick={onClick}>
      {isActive && <span className="mic-pulse-ring" />}
      <span className="mic-icon">{isActive ? "⏹" : "🎙"}</span>
    </button>
  );
}

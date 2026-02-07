"use client";

import { useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Mic, Square, Loader2 } from "lucide-react";

/* ── Types ── */
interface AgentOrbProps {
  /** idle | listening | thinking | speaking */
  status: "idle" | "listening" | "thinking" | "speaking";
  onClick: () => void;
}

/* ── Colour map per status ── */
const palette = {
  idle: { core: "#6366f1", glow: "rgba(99,102,241,0.35)", ring: "rgba(99,102,241,0.18)" },
  listening: { core: "#ef4444", glow: "rgba(239,68,68,0.4)", ring: "rgba(239,68,68,0.2)" },
  thinking: { core: "#8b5cf6", glow: "rgba(139,92,246,0.4)", ring: "rgba(139,92,246,0.18)" },
  speaking: { core: "#22c55e", glow: "rgba(34,197,94,0.4)", ring: "rgba(34,197,94,0.18)" },
};

const statusLabel: Record<AgentOrbProps["status"], string> = {
  idle: "Tap to speak",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

export default function AgentOrb({ status, onClick }: AgentOrbProps) {
  const c = palette[status];
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  /* ── Audio ring visualizer (canvas) ── */
  const drawRings = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = canvas.width;
    const cx = size / 2;
    const cy = size / 2;
    const t = Date.now() / 1000;

    ctx.clearRect(0, 0, size, size);

    // Draw concentric animated rings
    const ringCount = status === "listening" ? 5 : status === "speaking" ? 4 : 3;
    for (let i = 0; i < ringCount; i++) {
      const baseRadius = 52 + i * 14;
      const wobble =
        status === "idle"
          ? Math.sin(t * 0.8 + i * 0.6) * 2
          : status === "listening"
            ? Math.sin(t * 3 + i * 1.2) * (6 + i * 2)
            : status === "speaking"
              ? Math.sin(t * 2.5 + i * 0.9) * (5 + i * 1.5)
              : Math.sin(t * 1.5 + i * 0.8) * 3;

      const radius = baseRadius + wobble;
      const alpha = status === "idle" ? 0.06 + i * 0.02 : 0.1 + i * 0.03;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle =
        status === "idle"
          ? `rgba(99,102,241,${alpha})`
          : status === "listening"
            ? `rgba(239,68,68,${alpha})`
            : status === "speaking"
              ? `rgba(34,197,94,${alpha})`
              : `rgba(139,92,246,${alpha})`;
      ctx.lineWidth = status === "listening" ? 1.5 : 1;
      ctx.stroke();
    }

    // Rotating arc accent
    if (status !== "idle") {
      const arcRadius = 48;
      ctx.beginPath();
      const start = t * 2;
      ctx.arc(cx, cy, arcRadius, start, start + Math.PI * 0.6);
      ctx.strokeStyle = c.ring;
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.stroke();
    }

    rafRef.current = requestAnimationFrame(drawRings);
  }, [status, c.ring]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = 240 * dpr;
      canvas.height = 240 * dpr;
      canvas.getContext("2d")?.scale(dpr, dpr);
    }
    rafRef.current = requestAnimationFrame(drawRings);
    return () => cancelAnimationFrame(rafRef.current);
  }, [drawRings]);

  return (
    <div className="agent-orb-wrapper">
      {/* Canvas ring layer */}
      <canvas
        ref={canvasRef}
        className="agent-orb-canvas"
        style={{ width: 240, height: 240 }}
      />

      {/* Animated glow backdrop */}
      <motion.div
        className="agent-orb-glow"
        animate={{
          boxShadow: `0 0 ${status === "idle" ? 40 : 80}px ${status === "idle" ? 20 : 40}px ${c.glow}`,
          scale: status === "idle" ? 1 : [1, 1.08, 1],
        }}
        transition={{
          scale: { repeat: Infinity, duration: status === "listening" ? 0.8 : 1.5, ease: "easeInOut" },
          boxShadow: { duration: 0.4 },
        }}
      />

      {/* Pulse rings (listening/speaking) */}
      <AnimatePresence>
        {(status === "listening" || status === "speaking") && (
          <>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={`pulse-${i}`}
                className="agent-orb-pulse-ring"
                initial={{ scale: 1, opacity: 0.4 }}
                animate={{ scale: [1, 2.2], opacity: [0.3, 0] }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  delay: i * 0.6,
                  ease: "easeOut",
                }}
                style={{ borderColor: c.core }}
              />
            ))}
          </>
        )}
      </AnimatePresence>

      {/* Core button */}
      <motion.button
        className="agent-orb-core"
        onClick={onClick}
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.94 }}
        animate={{
          background: `radial-gradient(circle at 35% 35%, ${c.core}, ${c.core}dd)`,
          boxShadow: `0 0 30px ${c.glow}, inset 0 1px 0 rgba(255,255,255,0.15)`,
        }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      >
        <AnimatePresence mode="wait">
          {status === "idle" && (
            <motion.div
              key="mic"
              initial={{ scale: 0, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0, rotate: 90 }}
              transition={{ type: "spring", stiffness: 400, damping: 15 }}
            >
              <Mic size={28} strokeWidth={2.2} />
            </motion.div>
          )}
          {status === "listening" && (
            <motion.div
              key="stop"
              initial={{ scale: 0, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0, rotate: 90 }}
              transition={{ type: "spring", stiffness: 400, damping: 15 }}
            >
              <Square size={22} strokeWidth={2.5} fill="white" />
            </motion.div>
          )}
          {status === "thinking" && (
            <motion.div
              key="thinking"
              initial={{ scale: 0 }}
              animate={{ scale: 1, rotate: 360 }}
              exit={{ scale: 0 }}
              transition={{ rotate: { repeat: Infinity, duration: 1.2, ease: "linear" }, scale: { type: "spring" } }}
            >
              <Loader2 size={28} strokeWidth={2.2} />
            </motion.div>
          )}
          {status === "speaking" && (
            <motion.div
              key="speaking"
              initial={{ scale: 0 }}
              animate={{ scale: [1, 1.15, 1] }}
              exit={{ scale: 0 }}
              transition={{ scale: { repeat: Infinity, duration: 0.8, ease: "easeInOut" } }}
              className="agent-orb-speaking-bars"
            >
              {/* Audio bars */}
              <svg width="28" height="28" viewBox="0 0 28 28">
                {[6, 11, 16, 21].map((x, i) => (
                  <motion.rect
                    key={i}
                    x={x}
                    rx={1.5}
                    width={3}
                    fill="white"
                    animate={{
                      y: [10, 4 + i * 2, 10],
                      height: [8, 20 - i * 3, 8],
                    }}
                    transition={{
                      repeat: Infinity,
                      duration: 0.6 + i * 0.1,
                      ease: "easeInOut",
                      delay: i * 0.1,
                    }}
                  />
                ))}
              </svg>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>

      {/* Status label */}
      <AnimatePresence mode="wait">
        <motion.p
          key={status}
          className="agent-orb-label"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
          style={{ color: c.core }}
        >
          {statusLabel[status]}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

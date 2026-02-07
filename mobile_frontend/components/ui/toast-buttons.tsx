"use client";

import { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle, AlertCircle, Info, X, AlertTriangle } from "lucide-react";

/* ── Types ── */
export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastData {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

export interface ToastProps {
  toast: ToastData;
  onDismiss: (id: string) => void;
}

/* ── Icons by type ── */
const iconMap: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={18} />,
  error: <AlertCircle size={18} />,
  warning: <AlertTriangle size={18} />,
  info: <Info size={18} />,
};

/* ── Colour tokens ── */
const colorMap: Record<ToastType, { bg: string; border: string; text: string; icon: string }> = {
  success: {
    bg: "rgba(34, 197, 94, 0.12)",
    border: "rgba(34, 197, 94, 0.25)",
    text: "#4ade80",
    icon: "#22c55e",
  },
  error: {
    bg: "rgba(239, 68, 68, 0.12)",
    border: "rgba(239, 68, 68, 0.25)",
    text: "#f87171",
    icon: "#ef4444",
  },
  warning: {
    bg: "rgba(234, 179, 8, 0.12)",
    border: "rgba(234, 179, 8, 0.25)",
    text: "#facc15",
    icon: "#eab308",
  },
  info: {
    bg: "rgba(99, 102, 241, 0.12)",
    border: "rgba(99, 102, 241, 0.25)",
    text: "#a5b4fc",
    icon: "#6366f1",
  },
};

/* ── Single Toast ── */
export function Toast({ toast, onDismiss }: ToastProps) {
  const c = colorMap[toast.type];

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration ?? 4000);
    return () => clearTimeout(timer);
  }, [toast, onDismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 400, damping: 28 }}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 16px",
        borderRadius: 12,
        border: `1px solid ${c.border}`,
        background: c.bg,
        backdropFilter: "blur(12px)",
        color: c.text,
        fontSize: 14,
        fontWeight: 500,
        maxWidth: 360,
        width: "100%",
        boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
      }}
    >
      <span style={{ color: c.icon, flexShrink: 0 }}>{iconMap[toast.type]}</span>
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        style={{
          background: "none",
          border: "none",
          color: c.text,
          cursor: "pointer",
          padding: 2,
          opacity: 0.6,
          flexShrink: 0,
        }}
      >
        <X size={14} />
      </button>
    </motion.div>
  );
}

/* ── Toast Container (renders all active toasts) ── */
export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastData[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      style={{
        position: "fixed",
        top: 56,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((t) => (
          <div key={t.id} style={{ pointerEvents: "auto" }}>
            <Toast toast={t} onDismiss={onDismiss} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}

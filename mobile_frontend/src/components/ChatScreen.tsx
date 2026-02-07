"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAccount, useSendTransaction } from "wagmi";
import { parseEther } from "viem";
import { useConversation } from "@elevenlabs/react";
import { motion, AnimatePresence } from "motion/react";
import { History, X, Plus, MessageSquare } from "lucide-react";
import AgentOrb from "./AgentOrb";
import { useToast } from "./ToastProvider";

/* ── Types ── */
interface TranscriptLine {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ConvSummary {
  id: string;
  title: string | null;
}

type OrbStatus = "idle" | "listening" | "thinking" | "speaking";

/* ─────────────────────────────────────────────────── */
export default function ChatScreen() {
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [orbStatus, setOrbStatus] = useState<OrbStatus>("idle");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConvSummary[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { address } = useAccount();
  const { sendTransactionAsync } = useSendTransaction();
  const { showToast } = useToast();

  // Auto-scroll transcript to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [transcript]);

  // Load conversations when sidebar opens
  useEffect(() => {
    if (sidebarOpen) {
      fetch("/api/chat")
        .then((r) => r.json())
        .then((sessions: any[]) => {
          if (Array.isArray(sessions))
            setConversations(sessions.map((s: any) => ({ id: s.id, title: s.title })));
        })
        .catch(() => {});
    }
  }, [sidebarOpen]);

  const addLine = useCallback((role: TranscriptLine["role"], content: string) => {
    setTranscript((p) => [
      ...p,
      { id: crypto.randomUUID(), role, content, timestamp: new Date() },
    ]);
  }, []);

  /* ── ElevenLabs ── */
  const conversation = useConversation({
    onConnect: () => {
      setOrbStatus("listening");
      showToast("Connected – start speaking", "success", 2000);
    },
    onDisconnect: () => {
      setOrbStatus("idle");
    },
    onMessage: (msg: { message: string; source: string }) => {
      const role = msg.source === "user" ? "user" : "assistant";
      addLine(role as "user" | "assistant", msg.message);
      if (role === "assistant") setOrbStatus("speaking");
    },
    onError: (err: unknown) => {
      console.error("ElevenLabs error:", err);
      showToast("Voice connection error", "error");
      setOrbStatus("idle");
    },
  });

  const toggleVoice = async () => {
    if (orbStatus === "listening" || orbStatus === "speaking") {
      await conversation.endSession();
      setOrbStatus("idle");
    } else {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        setOrbStatus("thinking");
        await conversation.startSession({
          agentId: process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID ?? "",
          dynamicVariables: { wallet_address: address ?? "" },
          clientTools: {
            transferFunds: async ({ amount, to }: { amount: string; to: string }) => {
              try {
                const hash = await sendTransactionAsync({
                  to: to as `0x${string}`,
                  value: parseEther(amount),
                });
                showToast("Transaction sent!", "success");
                return `Transaction sent: ${hash}`;
              } catch (e: any) {
                showToast("Transfer failed", "error");
                return `Transfer failed: ${e.message}`;
              }
            },
            getWalletAddress: async () => address ?? "No wallet connected",
          },
        });
      } catch {
        showToast("Microphone access denied", "warning");
        setOrbStatus("idle");
      }
    }
  };

  return (
    <div className="chat-layout">
      {/* ─── Header bar (history + title + address) ─── */}
      <motion.header
        className="chat-header"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <button className="chat-header-btn" onClick={() => setSidebarOpen(true)}>
          <History size={18} />
        </button>
        <motion.span
          className="chat-header-title"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          SOTA Butler
        </motion.span>
        <div className="chat-header-right">
          {address && (
            <span className="chat-header-addr">
              {address.slice(0, 6)}…{address.slice(-4)}
            </span>
          )}
        </div>
      </motion.header>

      {/* ─── Transcript area (always visible, scrollable) ─── */}
      <div className="transcript-area" ref={scrollRef}>
        {transcript.length === 0 ? (
          <div className="transcript-empty">
            <AnimatePresence>
              <motion.div
                className="transcript-empty-content"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5 }}
              >
                <p className="transcript-empty-title">
                  Hello{address ? `, ${address.slice(0, 6)}…` : ""}
                </p>
                <p className="transcript-empty-sub">
                  Your AI concierge is ready. Tap the orb below to begin.
                </p>
              </motion.div>
            </AnimatePresence>
          </div>
        ) : (
          <div className="transcript-messages-list">
            {transcript.map((line, i) => (
              <motion.div
                key={line.id}
                className={`transcript-msg ${line.role}`}
                initial={{ opacity: 0, y: 12, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.3, delay: i > transcript.length - 3 ? 0.05 : 0 }}
              >
                <span className="transcript-msg-role">
                  {line.role === "user" ? "You" : "Butler"}
                </span>
                <p className="transcript-msg-text">{line.content}</p>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Orb area (bottom) ─── */}
      <div className="orb-dock">
        <AgentOrb status={orbStatus} onClick={toggleVoice} />
      </div>

      {/* ─── History sidebar ─── */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.div
              className="sidebar-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
            />
            <motion.aside
              className="sidebar-panel"
              initial={{ x: -320, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -320, opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
            >
              <div className="sidebar-panel-header">
                <h3>Conversations</h3>
                <div className="sidebar-panel-actions">
                  <button
                    className="sidebar-panel-btn"
                    onClick={() => {
                      setSessionId(null);
                      setTranscript([]);
                      setSidebarOpen(false);
                    }}
                  >
                    <Plus size={18} />
                  </button>
                  <button className="sidebar-panel-btn" onClick={() => setSidebarOpen(false)}>
                    <X size={18} />
                  </button>
                </div>
              </div>
              <div className="sidebar-panel-list">
                {conversations.length === 0 && (
                  <p className="sidebar-panel-empty">No conversations yet</p>
                )}
                {conversations.map((c, i) => (
                  <motion.button
                    key={c.id}
                    className="sidebar-panel-item"
                    onClick={() => {
                      setSessionId(c.id);
                      setSidebarOpen(false);
                    }}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    whileHover={{ x: 4 }}
                  >
                    <MessageSquare size={14} />
                    <span>{c.title || "Untitled chat"}</span>
                  </motion.button>
                ))}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

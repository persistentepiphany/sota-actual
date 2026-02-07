"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAccount, useSendTransaction } from "wagmi";
import { parseEther } from "viem";
import { useConversation } from "@elevenlabs/react";
import { Sidebar } from "./Sidebar";
import MicFab from "./MicFab";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [textInput, setTextInput] = useState("");
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<{ id: string; title: string | null }[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { address } = useAccount();
  const { sendTransactionAsync } = useSendTransaction();

  // Scroll to bottom on new message
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Load conversations when sidebar opens
  useEffect(() => {
    if (isSidebarOpen) {
      fetch('/api/chat')
        .then((r) => r.json())
        .then((sessions: any[]) => {
          if (Array.isArray(sessions)) {
            setConversations(sessions.map((s: any) => ({ id: s.id, title: s.title })));
          }
        })
        .catch(() => {});
    }
  }, [isSidebarOpen]);

  const addMessage = useCallback((role: ChatMessage["role"], content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, content, timestamp: new Date() },
    ]);
  }, []);

  // ── ElevenLabs conversation hook ──
  const conversation = useConversation({
    onConnect: () => setIsListening(true),
    onDisconnect: () => {
      setIsListening(false);
      setIsSpeaking(false);
    },
    onMessage: (msg: { message: string; source: string }) => {
      addMessage(msg.source === "user" ? "user" : "assistant", msg.message);
    },
    onError: (err: unknown) => {
      console.error("ElevenLabs error:", err);
      addMessage("system", "Voice connection error.");
    },
  });

  const toggleVoice = async () => {
    if (isListening) {
      await conversation.endSession();
    } else {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        await conversation.startSession({
          agentId: process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID ?? "",
          dynamicVariables: {
            wallet_address: address ?? "",
          },
          clientTools: {
            transferFunds: async ({ amount, to }: { amount: string; to: string }) => {
              try {
                const hash = await sendTransactionAsync({
                  to: to as `0x${string}`,
                  value: parseEther(amount),
                });
                return `Transaction sent: ${hash}`;
              } catch (e: any) {
                return `Transfer failed: ${e.message}`;
              }
            },
            getWalletAddress: async () => {
              return address ?? "No wallet connected";
            },
          },
        });
      } catch {
        addMessage("system", "Microphone access denied.");
      }
    }
  };

  // ── Text send ──
  const sendText = async () => {
    const text = textInput.trim();
    if (!text) return;
    addMessage("user", text);
    setTextInput("");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          walletAddress: address ?? "",
          sessionId,
        }),
      });
      const data = await res.json();
      if (data.sessionId) setSessionId(data.sessionId);
      addMessage("assistant", data.reply ?? "No response.");
    } catch {
      addMessage("system", "Failed to reach Butler API.");
    }
  };

  return (
    <div className="chat-screen">
      {/* Drawer */}
      {isSidebarOpen && (
        <div className="drawer-overlay" onClick={() => setSidebarOpen(false)}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <Sidebar
              open={isSidebarOpen}
              conversations={conversations}
              onSelect={(id) => {
                setSessionId(id);
                setSidebarOpen(false);
              }}
              onClose={() => setSidebarOpen(false)}
              onNewChat={() => {
                setSessionId(null);
                setMessages([]);
                setSidebarOpen(false);
              }}
            />
          </div>
        </div>
      )}

      {/* Header */}
      <div className="chat-header">
        <button className="icon-btn" onClick={() => setSidebarOpen(true)}>☰</button>
        <h2 className="chat-title">Butler</h2>
        <div className="chat-header-spacer" />
      </div>

      {/* Messages */}
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <p className="chat-empty-title">Hello{address ? `, ${address.slice(0, 6)}…` : ""}!</p>
            <p className="chat-empty-sub">Ask your Butler anything, or tap the mic to speak.</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-bubble ${msg.role}`}>
            <p>{msg.content}</p>
            <span className="chat-bubble-time">
              {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        ))}
      </div>

      {/* Input bar */}
      <div className="chat-input-bar">
        <input
          className="chat-text-input"
          placeholder="Type a message…"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendText()}
        />
        <button className="send-btn" onClick={sendText} disabled={!textInput.trim()}>
          ➤
        </button>
      </div>

      {/* Floating mic FAB */}
      <MicFab isActive={isListening} onClick={toggleVoice} />
    </div>
  );
}

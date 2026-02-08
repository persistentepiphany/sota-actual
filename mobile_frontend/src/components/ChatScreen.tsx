"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAccount, useSendTransaction } from "wagmi";
import { parseEther, encodeFunctionData } from "viem";
import { useConversation } from "@elevenlabs/react";
import { motion, AnimatePresence } from "motion/react";
import { History, X, Plus, MessageSquare, Send } from "lucide-react";
import AgentOrb from "./AgentOrb";
import { useToast } from "./ToastProvider";

/* ── Config ── */
const FLARE_BUTLER_URL =
  process.env.NEXT_PUBLIC_FLARE_BUTLER_URL || "http://localhost:3001/api/flare";

/* ── FlareEscrow.fundJob ABI fragment (payable) ── */
const ESCROW_FUND_JOB_ABI = [
  {
    name: "fundJob",
    type: "function",
    stateMutability: "payable",
    inputs: [
      { name: "jobId", type: "uint256" },
      { name: "provider", type: "address" },
      { name: "usdBudget", type: "uint256" },
    ],
    outputs: [],
  },
] as const;

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

/** SSR-safe unique ID (avoids Webpack resolving Node crypto module) */
function newSessionId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback for SSR / older runtimes
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/* ── Bid Progress Bar Component (Glassmorphism Style) ── */
function BidProgressBar({ duration, onComplete }: { duration: number; onComplete?: () => void }) {
  const [progress, setProgress] = useState(0);
  const [timeLeft, setTimeLeft] = useState(duration);

  useEffect(() => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      const pct = Math.min((elapsed / duration) * 100, 100);
      setProgress(pct);
      setTimeLeft(Math.max(duration - elapsed, 0));

      if (pct >= 100) {
        clearInterval(interval);
        onComplete?.();
      }
    }, 100);
    return () => clearInterval(interval);
  }, [duration, onComplete]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10 }}
      className="transcript-msg assistant"
    >
      <span className="transcript-msg-role">Butler</span>
      <p className="transcript-msg-text">
        Let me find the best specialist for your request...
      </p>
      <div className="mt-2 w-full">
        <div
          className="h-1 rounded-full overflow-hidden"
          style={{ background: 'rgba(255, 255, 255, 0.08)' }}
        >
          <motion.div
            className="h-full rounded-full"
            style={{ background: 'linear-gradient(90deg, #6366f1, #a78bfa, #c084fc)' }}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3, ease: "linear" }}
          />
        </div>
        <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted, #64748b)' }}>
          {Math.ceil(timeLeft)}s remaining
        </p>
      </div>
    </motion.div>
  );
}

/* ── Task Execution Progress (styled as normal butler message) ── */
function TaskExecutionProgress({ message }: { message: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10 }}
      className="transcript-msg assistant"
    >
      <span className="transcript-msg-role">Butler</span>
      <p className="transcript-msg-text">
        {message}
        <span className="inline-flex ml-2 gap-0.5 align-middle">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="inline-block w-1 h-1 rounded-full bg-current opacity-50"
              animate={{ opacity: [0.3, 0.8, 0.3] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </span>
      </p>
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────── */
export default function ChatScreen() {
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [orbStatus, setOrbStatus] = useState<OrbStatus>("idle");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessionId, setSessionId] = useState(newSessionId);
  const [conversations, setConversations] = useState<ConvSummary[]>([]);
  const [bidProgress, setBidProgress] = useState<{ active: boolean; duration: number } | null>(null);
  const [taskExecution, setTaskExecution] = useState<{ active: boolean; message: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { address } = useAccount();
  const { sendTransactionAsync } = useSendTransaction();
  const { showToast } = useToast();
  const [textInput, setTextInput] = useState("");

  // Refs to avoid stale closures in addLine callback
  const sessionIdRef = useRef(sessionId);
  const addressRef = useRef(address);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { addressRef.current = address; }, [address]);
  const [isSending, setIsSending] = useState(false);

  // Auto-scroll transcript to bottom on new messages or progress bar or task execution
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [transcript, bidProgress, taskExecution]);

  // Load conversations when sidebar opens (filtered by wallet)
  useEffect(() => {
    if (sidebarOpen && address) {
      fetch(`/api/chat?wallet=${address}`)
        .then((r) => r.json())
        .then((sessions: any[]) => {
          if (Array.isArray(sessions))
            setConversations(sessions.map((s: any) => ({ id: s.id, title: s.title })));
        })
        .catch(() => {});
    }
  }, [sidebarOpen, address]);

  const addLine = useCallback((role: TranscriptLine["role"], content: string) => {
    setTranscript((p) => [
      ...p,
      { id: crypto.randomUUID(), role, content, timestamp: new Date() },
    ]);
    // Persist to Firestore via API (fire-and-forget)
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: sessionIdRef.current,
        role,
        text: content,
        wallet: addressRef.current,
      }),
    }).catch(() => {});
  }, []);

  /* ── Post job JSON to backend marketplace ── */
  const postJobToMarketplace = useCallback(async (jobData: Record<string, any>) => {
    console.log("🚀 Posting job to marketplace:", jobData);
    // Normalize: if theme_technology_focus is a string, split to array
    if (typeof jobData.theme_technology_focus === "string") {
      jobData.theme_technology_focus = jobData.theme_technology_focus
        .split(/[/,]+/)
        .map((s: string) => s.trim())
        .filter(Boolean);
    }
    // Attach wallet address
    if (address) jobData.wallet_address = address;
    // Ensure budget_usd is set (USD value — FTSO converts to C2FLR on-chain)
    if (!jobData.budget_usd) {
      jobData.budget_usd = 0.02; // ~2 C2FLR at current FTSO rate
    }
    
    // Show progress bar during bid collection (15 seconds)
    setBidProgress({ active: true, duration: 15 });
    
    try {
      const res = await fetch(`${FLARE_BUTLER_URL}/marketplace/post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(jobData),
      });
      
      // Hide progress bar
      setBidProgress(null);
      
      if (!res.ok) throw new Error(`Post failed: ${res.statusText}`);
      const data = await res.json();
      console.log("✅ Marketplace post result:", data);

      // ── Parse result JSON to extract escrow info ──
      let escrowInfo: any = null;
      let jobResult: any = null;
      try {
        jobResult = typeof data.message === "string" ? JSON.parse(data.message) : data.message;
        escrowInfo = jobResult?.escrow;
      } catch {
        // message is not JSON, that's fine
      }

      // ── Fund escrow from user's wallet if needed ──
      if (escrowInfo?.needs_user_funding && escrowInfo?.address && escrowInfo?.flr_required && address) {
        const escrowAddr = escrowInfo.address as `0x${string}`;
        const flrRequired = escrowInfo.flr_required;
        const jobId = jobResult?.on_chain_job_id;
        const boardJobId = jobResult?.job_id;
        // Use winner address if valid, otherwise use the user's address (poster = provider for self-service)
        const rawWinnerAddr = jobResult?.winning_bid?.address;
        const winnerAddr = (rawWinnerAddr && rawWinnerAddr !== "0x0" && rawWinnerAddr.length === 42) 
          ? rawWinnerAddr 
          : address;
        const budgetUsd = escrowInfo.budget_usd || 0.02;
        const bidPrice = jobResult?.winning_bid?.price_flr || flrRequired;
        const bidderName = jobResult?.winning_bid?.bidder || "specialist";

        // Notify user about accepted bid
        addLine("assistant", `I've found a ${bidderName} for your request. The cost will be ${bidPrice.toFixed(4)} C2FLR (~$${budgetUsd} USD).`);

        console.log(`🔒 Funding escrow: ${flrRequired} C2FLR ($${budgetUsd} USD via FTSO) → ${escrowAddr} for job #${jobId}`);
        addLine("assistant", `Please confirm ${flrRequired.toFixed(4)} C2FLR in your wallet to proceed.`);

        try {
          // Encode fundJob(jobId, provider, usdBudget)
          const callData = encodeFunctionData({
            abi: ESCROW_FUND_JOB_ABI,
            functionName: "fundJob",
            args: [
              BigInt(jobId),
              winnerAddr as `0x${string}`,
              parseEther(String(budgetUsd)),
            ],
          });

          const txHash = await sendTransactionAsync({
            to: escrowAddr,
            data: callData,
            value: parseEther(String(flrRequired)),
          });

          console.log("✅ Escrow funded! tx:", txHash);
          showToast("Escrow funded! Starting task...", "success");
          addLine("assistant", `Escrow funded! ${Number(flrRequired).toFixed(4)} C2FLR locked on-chain. Starting task now...`);

          // ── Execute job after escrow funded ──
          setTaskExecution({ active: true, message: "Searching for results..." });
          
          try {
            const execRes = await fetch(`${FLARE_BUTLER_URL}/marketplace/execute/${boardJobId}`, {
              method: "POST",
            });
            
            setTaskExecution(null);
            
            if (execRes.ok) {
              const execData = await execRes.json();
              if (execData.formatted_results) {
                addLine("assistant", execData.formatted_results);
              } else {
                addLine("assistant", "Your request has been completed. The specialist has finished the task.");
              }
            } else {
              addLine("assistant", "The task is being processed. I'll have results for you shortly.");
            }
          } catch (execErr) {
            console.error("Execution failed:", execErr);
            setTaskExecution(null);
            addLine("assistant", "I'm still working on your request. Please check back in a moment.");
          }

          return `Job posted and escrow funded (${flrRequired.toFixed(2)} C2FLR locked). Tx: ${txHash}`;
        } catch (fundErr: any) {
          console.error("❌ Escrow funding failed:", fundErr);
          showToast("Escrow funding declined", "warning");
          addLine("assistant", `⚠️ Payment was declined. The specialist is assigned but won't start until payment is locked.`);
          return "Job posted but escrow funding was not completed.";
        }
      }

      showToast("Job posted to marketplace!", "success");
      return data.message || "Job posted successfully";
    } catch (err: any) {
      setBidProgress(null);
      setTaskExecution(null);
      console.error("❌ Marketplace post error:", err);
      showToast("Failed to post job", "error");
      return `Failed to post job: ${err.message}`;
    }
  }, [address, showToast, sendTransactionAsync, addLine]);

  /* ── Try to extract & auto-post JSON from assistant text ── */
  const interceptJsonJob = useCallback(async (text: string) => {
    // Match patterns like: job { "task": ... } or {"task": ...}
    const jsonMatch = text.match(/\{[\s\S]*"task"\s*:\s*"[^"]+"[\s\S]*\}/);
    if (!jsonMatch) return;
    try {
      const parsed = JSON.parse(jsonMatch[0]);
      if (parsed.task) {
        console.log("🔍 Intercepted JSON job from assistant text:", parsed);
        // Don't add duplicate message - postJobToMarketplace shows progress bar
        await postJobToMarketplace(parsed);
      }
    } catch {
      // Not valid JSON, ignore
    }
  }, [postJobToMarketplace]);

  /* ── ElevenLabs ── */
  const conversation = useConversation({
    onConnect: () => {
      console.log("🎙️ ElevenLabs connected");
      setOrbStatus("listening");
      showToast("Connected – start speaking", "success", 2000);
    },
    onDisconnect: () => {
      console.log("🔌 ElevenLabs disconnected");
      setOrbStatus("idle");
    },
    onMessage: (msg: { message: string; source: string }) => {
      console.log("💬 ElevenLabs message:", msg);
      const role = msg.source === "user" ? "user" : "assistant";
      addLine(role as "user" | "assistant", msg.message);
      if (role === "assistant") {
        setOrbStatus("speaking");
        // Auto-intercept if ElevenLabs outputs JSON in its text
        interceptJsonJob(msg.message);
      }
    },
    onError: (err: unknown) => {
      console.error("❌ ElevenLabs error:", err);
      showToast("Voice connection error", "error");
      setOrbStatus("idle");
    },
    // Debug: catch any unhandled tool calls
    onUnhandledClientToolCall: (toolCall: any) => {
      console.error("⚠️ UNHANDLED client tool call:", toolCall);
      showToast(`Unhandled tool: ${toolCall?.tool_name || toolCall?.name || "unknown"}`, "warning");
    },
    // Debug: log all events
    onDebug: (info: unknown) => {
      console.log("🔍 ElevenLabs debug:", info);
    },
  });

  const toggleVoice = async () => {
    if (orbStatus === "listening" || orbStatus === "speaking") {
      await conversation.endSession();
      setOrbStatus("idle");
    } else {
      if (!address) {
        showToast("Connect your wallet first", "warning");
        return;
      }
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        setOrbStatus("thinking");
        await conversation.startSession({
          agentId: process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID ?? "",
          dynamicVariables: { wallet_address: address ?? "" },
          clientTools: {
            /* ── Post job to marketplace (called by ElevenLabs when JSON is ready) ── */
            post_job: async (params: Record<string, any>) => {
              console.log("📤 ElevenLabs called post_job with params:", params);
              
              // Handle both formats:
              // 1. Direct object: { task, location, ... }
              // 2. Wrapped JSON string: { job_data: '{"task": ...}' }
              let jobData: Record<string, any>;
              if (typeof params.job_data === "string") {
                try {
                  jobData = JSON.parse(params.job_data);
                  console.log("📦 Parsed job_data JSON:", jobData);
                } catch {
                  console.error("❌ Failed to parse job_data JSON:", params.job_data);
                  return "Error: Invalid job data format";
                }
              } else if (params.job_data && typeof params.job_data === "object") {
                jobData = params.job_data;
              } else {
                // Direct format — params IS the job data
                jobData = params;
              }

              // Don't add duplicate message - postJobToMarketplace shows progress bar
              const result = await postJobToMarketplace(jobData);
              return result;
            },

            /* ── Bridge to OpenAI Butler backend ── */
            query_butler: async ({ query }: { query: string }) => {
              console.log("📤 Sending to Flare Butler (OpenAI):", query);
              try {
                const res = await fetch(`${FLARE_BUTLER_URL}/chat`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ query, timestamp: Date.now() }),
                });
                if (!res.ok) throw new Error(`Butler error: ${res.statusText}`);
                const data = await res.json();
                console.log("✅ Butler Agent response:", data);

                // If Butler posted a job on-chain, trigger escrow funding
                if (data.job_posted) {
                  console.log("📦 Job posted via voice query_butler:", data.job_posted);
                  const jp = data.job_posted;
                  const escrowInfo = jp.escrow;
                  if (escrowInfo?.needs_user_funding && escrowInfo?.address && escrowInfo?.flr_required && address) {
                    const escrowAddr = escrowInfo.address as `0x${string}`;
                    const flrRequired = escrowInfo.flr_required;
                    const jobId = jp.on_chain_job_id;
                    const winnerAddr = jp.winning_bid?.address || address;
                    const budgetUsd = escrowInfo.budget_usd || 0.02;
                    addLine("assistant", `🔒 Locking ${Number(flrRequired).toFixed(4)} C2FLR in escrow…`);
                    try {
                      const callData = encodeFunctionData({
                        abi: ESCROW_FUND_JOB_ABI,
                        functionName: "fundJob",
                        args: [BigInt(jobId), winnerAddr as `0x${string}`, parseEther(String(budgetUsd))],
                      });
                      const txHash = await sendTransactionAsync({
                        to: escrowAddr,
                        data: callData,
                        value: parseEther(String(flrRequired)),
                      });
                      console.log("✅ Escrow funded via voice! tx:", txHash);
                      showToast("Escrow funded!", "success");
                      addLine("assistant", `✅ Escrow funded! ${Number(flrRequired).toFixed(4)} C2FLR locked.`);
                    } catch (fundErr: any) {
                      console.error("❌ Escrow funding failed:", fundErr);
                      showToast("Escrow funding declined", "warning");
                    }
                  }
                }

                return data.response || data.message || "Request processed";
              } catch (err: any) {
                console.error("❌ Butler Agent error:", err);
                return `I had trouble connecting to the butler agent. ${err.message}`;
              }
            },

            /* ── FTSO price quote ── */
            get_flr_quote: async ({ usdAmount }: { usdAmount: number }) => {
              console.log("💰 Getting FTSO quote for $", usdAmount);
              try {
                const res = await fetch(`${FLARE_BUTLER_URL}/price?usd=${usdAmount}`);
                const data = await res.json();
                return `$${usdAmount} USD ≈ ${data.flr_amount} FLR (FTSO rate: $${data.flr_usd_price})`;
              } catch (err) {
                return `Error getting quote: ${err}`;
              }
            },

            /* ── Marketplace job listings ── */
            get_job_listings: async ({ filters }: { filters?: any }) => {
              console.log("📋 Fetching marketplace jobs:", filters);
              try {
                const res = await fetch(`${FLARE_BUTLER_URL}/marketplace/jobs`);
                const data = await res.json();
                if (data.jobs && data.jobs.length > 0) {
                  const summary = data.jobs
                    .map(
                      (j: any) =>
                        `Job ${j.job_id}: ${j.description} (${j.status}, budget: ${j.budget_flr} C2FLR)`
                    )
                    .join("; ");
                  return `Found ${data.total} jobs on the marketplace: ${summary}`;
                }
                return "No jobs currently on the marketplace.";
              } catch (err) {
                return `Error fetching marketplace jobs: ${err}`;
              }
            },

            /* ── Wallet tools ── */
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

  /* ── Send a typed message directly to the Butler backend ── */
  const handleSendText = async () => {
    const msg = textInput.trim();
    if (!msg || isSending) return;
    if (!address) {
      showToast("Connect your wallet first", "warning");
      return;
    }
    setTextInput("");
    addLine("user", msg);
    setIsSending(true);
    setOrbStatus("thinking");
    try {
      const res = await fetch(`${FLARE_BUTLER_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: msg, timestamp: Date.now() }),
      });
      if (!res.ok) throw new Error(`Butler error: ${res.statusText}`);
      const data = await res.json();
      console.log("✅ Butler text response:", data);
      addLine("assistant", data.response || data.message || "Request processed");

      // ── If a job was posted on-chain, handle escrow funding ──
      if (data.job_posted) {
        console.log("📦 Job posted on-chain by Butler:", data.job_posted);
        const jp = data.job_posted;
        const escrowInfo = jp.escrow;
        if (escrowInfo?.needs_user_funding && escrowInfo?.address && escrowInfo?.flr_required && address) {
          const escrowAddr = escrowInfo.address as `0x${string}`;
          const flrRequired = escrowInfo.flr_required;
          const jobId = jp.on_chain_job_id;
          const winnerAddr = jp.winning_bid?.address || address;
          const budgetUsd = escrowInfo.budget_usd || 0.02;

          console.log(`🔒 Funding escrow: ${flrRequired} C2FLR ($${budgetUsd} USD) → ${escrowAddr} for job #${jobId}`);
          addLine("assistant", `🔒 Locking ${Number(flrRequired).toFixed(4)} C2FLR in escrow. Please confirm in your wallet…`);

          try {
            const callData = encodeFunctionData({
              abi: ESCROW_FUND_JOB_ABI,
              functionName: "fundJob",
              args: [
                BigInt(jobId),
                winnerAddr as `0x${string}`,
                parseEther(String(budgetUsd)),
              ],
            });
            const txHash = await sendTransactionAsync({
              to: escrowAddr,
              data: callData,
              value: parseEther(String(flrRequired)),
            });
            console.log("✅ Escrow funded! tx:", txHash);
            showToast("Escrow funded! Starting task...", "success");
            addLine("assistant", `✅ Escrow funded! ${Number(flrRequired).toFixed(4)} C2FLR locked on-chain. Starting task now...`);

            // Trigger job execution after escrow funded
            const boardJobId = jp.job_id;
            if (boardJobId) {
              setTaskExecution({ active: true, message: "Generating your market analysis..." });
              try {
                const execRes = await fetch(`${FLARE_BUTLER_URL}/marketplace/execute/${boardJobId}`, {
                  method: "POST",
                });
                setTaskExecution(null);
                if (execRes.ok) {
                  const execData = await execRes.json();
                  if (execData.formatted_results) {
                    addLine("assistant", execData.formatted_results);
                  } else {
                    addLine("assistant", "Your request has been completed.");
                  }
                } else {
                  addLine("assistant", "The task is being processed. I'll have results for you shortly.");
                }
              } catch (execErr) {
                console.error("Execution failed:", execErr);
                setTaskExecution(null);
                addLine("assistant", "I'm still working on your request. Please check back shortly.");
              }
            }
          } catch (fundErr: any) {
            console.error("❌ Escrow funding failed:", fundErr);
            showToast("Escrow funding declined", "warning");
            addLine("assistant", `⚠️ Job posted but escrow funding was declined. The specialist is still assigned.`);
          }
        }
      }
    } catch (err: any) {
      console.error("❌ Butler text error:", err);
      addLine("assistant", `Sorry, I couldn't reach the butler. ${err.message}`);
      showToast("Backend connection error", "error");
    } finally {
      setIsSending(false);
      setOrbStatus("idle");
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
                  {address
                    ? "Your AI concierge is ready. Tap the orb or type below."
                    : "Connect your wallet to get started."}
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
            {/* Bid collection progress bar */}
            <AnimatePresence>
              {bidProgress?.active && (
                <BidProgressBar
                  duration={bidProgress.duration}
                  onComplete={() => setBidProgress(null)}
                />
              )}
            </AnimatePresence>
            {/* Task execution progress */}
            <AnimatePresence>
              {taskExecution?.active && (
                <TaskExecutionProgress message={taskExecution.message} />
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* ─── Orb area (bottom) ─── */}
      <div className="orb-dock">
        <AgentOrb status={orbStatus} onClick={toggleVoice} />
      </div>

      {/* ─── Text input bar ─── */}
      <div className="text-input-bar">
        <input
          className="text-input-field"
          type="text"
          placeholder="Type a message…"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSendText();
            }
          }}
          disabled={isSending}
        />
        <button
          className="text-input-send"
          onClick={handleSendText}
          disabled={isSending || !textInput.trim()}
        >
          <Send size={18} />
        </button>
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
                      setSessionId(newSessionId());
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
                    className={`sidebar-panel-item${c.id === sessionId ? " active" : ""}`}
                    onClick={async () => {
                      try {
                        const res = await fetch(`/api/chat?sessionId=${c.id}`);
                        const msgs = await res.json();
                        if (Array.isArray(msgs)) {
                          setTranscript(
                            msgs.map((m: any) => ({
                              id: m.id,
                              role: m.role as "user" | "assistant",
                              content: m.text,
                              timestamp: new Date(m.createdAt),
                            }))
                          );
                        }
                      } catch {
                        // If fetch fails, just switch session
                      }
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

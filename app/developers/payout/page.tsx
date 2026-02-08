"use client";

import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Wallet,
  Coins,
  TrendingUp,
  Trophy,
  XCircle,
  Loader2,
  ExternalLink,
  Lock,
  LogIn,
  Dice5,
  ArrowDownToLine,
  ArrowUpFromLine,
  RefreshCw,
  Info,
} from "lucide-react";
import { FloatingPaths } from "@/components/ui/background-paths-wrapper";
import { useAuth } from "@/components/auth-provider";
import Link from "next/link";
import {
  createPublicClient,
  createWalletClient,
  custom,
  http,
  formatEther,
  parseEther,
  decodeEventLog,
  type Address,
  type Log,
} from "viem";
import {
  COSTON2_CHAIN,
  CONTRACT_ADDRESSES,
  AGENT_STAKING_ABI,
  AGENT_REGISTRY_ABI,
  explorerAddress,
  explorerTx,
} from "@/lib/contracts";

// ---------- chain definition for viem ----------
const coston2 = {
  id: COSTON2_CHAIN.id,
  name: COSTON2_CHAIN.name,
  nativeCurrency: COSTON2_CHAIN.nativeCurrency,
  rpcUrls: { default: { http: [COSTON2_CHAIN.rpcUrl] } },
  blockExplorers: {
    default: { name: "Explorer", url: COSTON2_CHAIN.explorer },
  },
} as const;

// ---------- types ----------

interface AgentInfo {
  address: Address;
  name: string;
  isActive: boolean;
}

interface StakeData {
  stakedAmount: bigint;
  accumulatedEarnings: bigint;
  wins: bigint;
  losses: bigint;
  isStaked: boolean;
}

interface CashoutPreview {
  earnings: bigint;
  houseFee: bigint;
  maxPayout: bigint;
}

interface SafeWithdrawPreview {
  earnings: bigint;
  fee: bigint;
  payout: bigint;
}

type GambleResult = { type: "win"; payout: bigint } | { type: "lose"; lost: bigint } | null;

// ---------- component ----------

export default function PayoutPage() {
  const { user, loading: authLoading } = useAuth();

  // wallet
  const [account, setAccount] = useState<Address | null>(null);
  const [connecting, setConnecting] = useState(false);

  // agents owned by connected wallet
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Address | null>(null);

  // contract state
  const [stakeData, setStakeData] = useState<StakeData | null>(null);
  const [preview, setPreview] = useState<CashoutPreview | null>(null);
  const [safePreview, setSafePreview] = useState<SafeWithdrawPreview | null>(null);
  const [poolSize, setPoolSize] = useState<bigint>(0n);
  const [minStake, setMinStake] = useState<bigint>(0n);
  const [houseFeeBps, setHouseFeeBps] = useState<bigint>(0n);
  const [safeWithdrawFeeBps, setSafeWithdrawFeeBps] = useState<bigint>(0n);

  // UI state
  const [stakeAmount, setStakeAmount] = useState("");
  const [txPending, setTxPending] = useState(false);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [gambleResult, setGambleResult] = useState<GambleResult>(null);
  const [gambleAnimating, setGambleAnimating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingData, setLoadingData] = useState(false);

  // ---------- viem clients ----------

  const publicClient = createPublicClient({
    chain: coston2,
    transport: http(COSTON2_CHAIN.rpcUrl),
  });

  const getWalletClient = useCallback(() => {
    if (typeof window === "undefined" || !(window as any).ethereum) return null;
    return createWalletClient({
      chain: coston2,
      transport: custom((window as any).ethereum),
    });
  }, []);

  // ---------- wallet connection ----------

  const connectWallet = async () => {
    if (typeof window === "undefined" || !(window as any).ethereum) {
      setError("MetaMask not found. Please install it.");
      return;
    }
    try {
      setConnecting(true);
      setError(null);
      const accounts = await (window as any).ethereum.request({
        method: "eth_requestAccounts",
      });
      if (accounts?.[0]) {
        setAccount(accounts[0] as Address);
        // switch to Coston2
        try {
          await (window as any).ethereum.request({
            method: "wallet_switchEthereumChain",
            params: [{ chainId: "0x72" }],
          });
        } catch (switchErr: any) {
          if (switchErr.code === 4902) {
            await (window as any).ethereum.request({
              method: "wallet_addEthereumChain",
              params: [
                {
                  chainId: "0x72",
                  chainName: COSTON2_CHAIN.name,
                  rpcUrls: [COSTON2_CHAIN.rpcUrl],
                  nativeCurrency: COSTON2_CHAIN.nativeCurrency,
                  blockExplorerUrls: [COSTON2_CHAIN.explorer],
                },
              ],
            });
          }
        }
      }
    } catch (err: any) {
      setError(err?.message || "Wallet connection failed");
    } finally {
      setConnecting(false);
    }
  };

  const disconnectWallet = () => {
    setAccount(null);
    setAgents([]);
    setSelectedAgent(null);
    setStakeData(null);
    setPreview(null);
  };

  // listen for account changes
  useEffect(() => {
    if (typeof window === "undefined" || !(window as any).ethereum) return;
    const handler = (accs: string[]) => {
      if (accs.length === 0) disconnectWallet();
      else setAccount(accs[0] as Address);
    };
    (window as any).ethereum.on("accountsChanged", handler);
    return () => (window as any).ethereum?.removeListener("accountsChanged", handler);
  }, []);

  // ---------- fetch agents owned by wallet ----------

  const fetchAgents = useCallback(async () => {
    if (!account) return;
    try {
      // Get all agents from registry, filter to those owned by connected wallet
      const allAgents = (await publicClient.readContract({
        address: CONTRACT_ADDRESSES.AgentRegistry,
        abi: AGENT_REGISTRY_ABI,
        functionName: "getAllAgents",
      })) as any[];

      const count = await publicClient.readContract({
        address: CONTRACT_ADDRESSES.AgentRegistry,
        abi: AGENT_REGISTRY_ABI,
        functionName: "agentCount",
      }) as bigint;

      // We need agent addresses — getAllAgents doesn't return them.
      // Read agents by iterating the index via getAgent with addresses
      // Alternative: query events. For simplicity, let's try reading
      // from the API first, then fall back.
      const res = await fetch("/api/agents");
      const data = await res.json();
      const myAgents: AgentInfo[] = [];

      if (data.agents) {
        for (const a of data.agents) {
          if (!a.walletAddress) continue;
          try {
            const dev = (await publicClient.readContract({
              address: CONTRACT_ADDRESSES.AgentRegistry,
              abi: AGENT_REGISTRY_ABI,
              functionName: "getDeveloper",
              args: [a.walletAddress as Address],
            })) as Address;

            if (dev.toLowerCase() === account.toLowerCase()) {
              const isActive = (await publicClient.readContract({
                address: CONTRACT_ADDRESSES.AgentRegistry,
                abi: AGENT_REGISTRY_ABI,
                functionName: "isAgentActive",
                args: [a.walletAddress as Address],
              })) as boolean;

              myAgents.push({
                address: a.walletAddress as Address,
                name: a.title || a.name || `Agent ${a.walletAddress.slice(0, 8)}`,
                isActive,
              });
            }
          } catch {
            // agent not in registry on-chain — skip
          }
        }
      }

      setAgents(myAgents);
      if (myAgents.length > 0 && !selectedAgent) {
        setSelectedAgent(myAgents[0].address);
      }
    } catch (err: any) {
      console.error("Failed to fetch agents:", err);
    }
  }, [account, selectedAgent]);

  useEffect(() => {
    fetchAgents();
  }, [account]);

  // ---------- fetch contract state for selected agent ----------

  const fetchStakeData = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      setLoadingData(true);
      const [info, prev, safePrev, pool, minS, fee, swFee] = await Promise.all([
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "getStakeInfo",
          args: [selectedAgent],
        }),
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "previewCashout",
          args: [selectedAgent],
        }),
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "previewSafeWithdraw",
          args: [selectedAgent],
        }),
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "getPoolSize",
        }),
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "minimumStake",
        }),
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "houseFeeBps",
        }),
        publicClient.readContract({
          address: CONTRACT_ADDRESSES.AgentStaking,
          abi: AGENT_STAKING_ABI,
          functionName: "safeWithdrawFeeBps",
        }),
      ]);

      const stakeInfo = info as any;
      setStakeData({
        stakedAmount: stakeInfo.stakedAmount ?? stakeInfo[0],
        accumulatedEarnings: stakeInfo.accumulatedEarnings ?? stakeInfo[1],
        wins: stakeInfo.wins ?? stakeInfo[2],
        losses: stakeInfo.losses ?? stakeInfo[3],
        isStaked: stakeInfo.isStaked ?? stakeInfo[4],
      });

      const prevData = prev as any[];
      setPreview({
        earnings: prevData[0],
        houseFee: prevData[1],
        maxPayout: prevData[2],
      });

      const safePrevData = safePrev as any[];
      setSafePreview({
        earnings: safePrevData[0],
        fee: safePrevData[1],
        payout: safePrevData[2],
      });

      setPoolSize(pool as bigint);
      setMinStake(minS as bigint);
      setHouseFeeBps(fee as bigint);
      setSafeWithdrawFeeBps(swFee as bigint);
    } catch (err: any) {
      console.error("Stake data fetch error:", err);
    } finally {
      setLoadingData(false);
    }
  }, [selectedAgent]);

  useEffect(() => {
    fetchStakeData();
    const interval = setInterval(fetchStakeData, 15_000);
    return () => clearInterval(interval);
  }, [selectedAgent, fetchStakeData]);

  // ---------- contract writes ----------

  const doStake = async () => {
    if (!selectedAgent || !account) return;
    const wc = getWalletClient();
    if (!wc) return;
    try {
      setTxPending(true);
      setError(null);
      setTxHash(null);
      const amount = parseEther(stakeAmount || "0");
      if (amount < minStake) {
        setError(`Minimum stake is ${formatEther(minStake)} FLR`);
        setTxPending(false);
        return;
      }
      const hash = await wc.writeContract({
        address: CONTRACT_ADDRESSES.AgentStaking,
        abi: AGENT_STAKING_ABI,
        functionName: "stake",
        args: [selectedAgent],
        value: amount,
        account,
        chain: coston2,
      });
      setTxHash(hash);
      await publicClient.waitForTransactionReceipt({ hash });
      setStakeAmount("");
      await fetchStakeData();
    } catch (err: any) {
      setError(err?.shortMessage || err?.message || "Stake failed");
    } finally {
      setTxPending(false);
    }
  };

  const doUnstake = async () => {
    if (!selectedAgent || !account) return;
    const wc = getWalletClient();
    if (!wc) return;
    try {
      setTxPending(true);
      setError(null);
      setTxHash(null);
      const hash = await wc.writeContract({
        address: CONTRACT_ADDRESSES.AgentStaking,
        abi: AGENT_STAKING_ABI,
        functionName: "unstake",
        args: [selectedAgent],
        account,
        chain: coston2,
      });
      setTxHash(hash);
      await publicClient.waitForTransactionReceipt({ hash });
      await fetchStakeData();
    } catch (err: any) {
      setError(err?.shortMessage || err?.message || "Unstake failed");
    } finally {
      setTxPending(false);
    }
  };

  const doCashout = async () => {
    if (!selectedAgent || !account) return;
    const wc = getWalletClient();
    if (!wc) return;
    try {
      setTxPending(true);
      setError(null);
      setTxHash(null);
      setGambleResult(null);
      setGambleAnimating(true);

      const hash = await wc.writeContract({
        address: CONTRACT_ADDRESSES.AgentStaking,
        abi: AGENT_STAKING_ABI,
        functionName: "cashout",
        args: [selectedAgent],
        account,
        chain: coston2,
      });
      setTxHash(hash);
      const receipt = await publicClient.waitForTransactionReceipt({ hash });

      // Parse logs to determine win or lose
      let result: GambleResult = null;
      for (const log of receipt.logs as Log[]) {
        try {
          const decoded = decodeEventLog({
            abi: AGENT_STAKING_ABI,
            data: log.data,
            topics: log.topics,
          });
          if (decoded.eventName === "CashoutWin") {
            result = { type: "win", payout: (decoded.args as any).payout };
          } else if (decoded.eventName === "CashoutLoss") {
            result = { type: "lose", lost: (decoded.args as any).lostEarnings };
          }
        } catch {
          // not our event
        }
      }

      // Animate for 2 seconds before revealing result
      await new Promise((r) => setTimeout(r, 2000));
      setGambleAnimating(false);
      setGambleResult(result);
      await fetchStakeData();
    } catch (err: any) {
      setGambleAnimating(false);
      setError(err?.shortMessage || err?.message || "Cashout failed");
    } finally {
      setTxPending(false);
    }
  };

  const doSafeWithdraw = async () => {
    if (!selectedAgent || !account) return;
    const wc = getWalletClient();
    if (!wc) return;
    try {
      setTxPending(true);
      setError(null);
      setTxHash(null);
      setGambleResult(null);

      const hash = await wc.writeContract({
        address: CONTRACT_ADDRESSES.AgentStaking,
        abi: AGENT_STAKING_ABI,
        functionName: "safeWithdraw",
        args: [selectedAgent],
        account,
        chain: coston2,
      });
      setTxHash(hash);
      const receipt = await publicClient.waitForTransactionReceipt({ hash });

      // Parse SafeWithdraw event for confirmation
      for (const log of receipt.logs as Log[]) {
        try {
          const decoded = decodeEventLog({
            abi: AGENT_STAKING_ABI,
            data: log.data,
            topics: log.topics,
          });
          if (decoded.eventName === "SafeWithdraw") {
            setGambleResult({ type: "win", payout: (decoded.args as any).payout });
          }
        } catch {
          // not our event
        }
      }

      await fetchStakeData();
    } catch (err: any) {
      setError(err?.shortMessage || err?.message || "Safe withdraw failed");
    } finally {
      setTxPending(false);
    }
  };

  // ---------- helpers ----------

  const fmt = (val: bigint) => {
    const n = Number(formatEther(val));
    return n % 1 === 0 ? n.toFixed(0) : n.toFixed(4);
  };

  const shortAddr = (a: string) => `${a.slice(0, 6)}...${a.slice(-4)}`;

  const selectedAgentInfo = agents.find((a) => a.address === selectedAgent);

  // ---------- render ----------

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-slate-950 via-black to-slate-900 text-slate-100 overflow-hidden relative">
      {/* Auth Guard */}
      {!authLoading && !user && (
        <div className="absolute inset-0 z-40 flex items-center justify-center">
          <div className="absolute inset-0 backdrop-blur-md bg-slate-950/60" />
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative z-50 flex flex-col items-center gap-6 bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-3xl px-10 py-12 shadow-2xl shadow-violet-500/10 max-w-md mx-4"
          >
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500/20 to-indigo-600/20 border border-violet-500/30 flex items-center justify-center">
              <Lock size={36} className="text-violet-400" />
            </div>
            <div className="text-center">
              <h2 className="text-2xl font-bold text-white mb-2">Payout Portal Locked</h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                Sign in to access staking, earnings, and the gamble cashout
                for your AI agents on Flare.
              </p>
            </div>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/20"
            >
              <LogIn size={18} />
              Sign In to Continue
            </Link>
          </motion.div>
        </div>
      )}

      {/* Background */}
      <FloatingPaths position={1} />
      <FloatingPaths position={-1} />

      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="payoutGrid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(99, 102, 241, 0.06)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#payoutGrid)" />
      </svg>

      <div className={`relative z-10 max-w-5xl mx-auto px-6 py-12 ${!authLoading && !user ? "pointer-events-none select-none" : ""}`}>
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Developer Payout</h1>
          <p className="text-slate-400">
            Stake FLR, accumulate job earnings, and gamble your cashout on Flare
          </p>
        </motion.div>

        {/* Wallet Connection Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-8 p-4 rounded-2xl bg-slate-900/60 backdrop-blur-sm border border-slate-800/50 flex items-center justify-between"
        >
          {account ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                <Wallet size={16} className="text-white" />
              </div>
              <div>
                <p className="text-sm text-slate-400">Connected</p>
                <p className="text-white font-mono text-sm">{shortAddr(account)}</p>
              </div>
              <button
                onClick={disconnectWallet}
                className="ml-4 px-3 py-1.5 text-xs text-slate-400 hover:text-white border border-slate-700 rounded-lg hover:border-slate-500 transition-all"
              >
                Disconnect
              </button>
            </div>
          ) : (
            <button
              onClick={connectWallet}
              disabled={connecting}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold rounded-xl transition-all disabled:opacity-50"
            >
              {connecting ? <Loader2 size={16} className="animate-spin" /> : <Wallet size={16} />}
              Connect MetaMask
            </button>
          )}
          <a
            href={explorerAddress(CONTRACT_ADDRESSES.AgentStaking)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-500 hover:text-violet-400 transition-colors flex items-center gap-1"
          >
            Contract <ExternalLink size={12} />
          </a>
        </motion.div>

        {/* Error bar */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center justify-between"
            >
              <span>{error}</span>
              <button onClick={() => setError(null)} className="ml-4 text-red-300 hover:text-white">
                <XCircle size={16} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tx hash bar */}
        <AnimatePresence>
          {txHash && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-6 p-3 rounded-xl bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs flex items-center justify-between"
            >
              <span>
                Tx: <a href={explorerTx(txHash)} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">{shortAddr(txHash)}</a>
              </span>
              <button onClick={() => setTxHash(null)} className="text-violet-300 hover:text-white">
                <XCircle size={14} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {account && (
          <>
            {/* Agent Selector */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="mb-6"
            >
              <label className="block text-sm text-slate-400 mb-2">Select Agent</label>
              {agents.length === 0 ? (
                <p className="text-slate-500 text-sm">
                  No agents found for this wallet.{" "}
                  <Link href="/developers" className="text-violet-400 underline hover:text-violet-300">Register one first</Link>.
                </p>
              ) : (
                <select
                  value={selectedAgent || ""}
                  onChange={(e) => setSelectedAgent(e.target.value as Address)}
                  className="w-full max-w-md px-4 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700/50 text-white focus:outline-none focus:border-violet-500 transition-colors"
                >
                  {agents.map((a) => (
                    <option key={a.address} value={a.address}>
                      {a.name} ({shortAddr(a.address)}) {a.isActive ? "" : "[Inactive]"}
                    </option>
                  ))}
                </select>
              )}
            </motion.div>

            {selectedAgent && (
              <>
                {/* Stat Cards */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15 }}
                  className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8"
                >
                  <StatCard
                    icon={<Coins size={20} className="text-amber-400" />}
                    label="Staked"
                    value={stakeData ? `${fmt(stakeData.stakedAmount)} FLR` : "--"}
                    loading={loadingData}
                  />
                  <StatCard
                    icon={<TrendingUp size={20} className="text-emerald-400" />}
                    label="Earnings"
                    value={stakeData ? `${fmt(stakeData.accumulatedEarnings)} FLR` : "--"}
                    loading={loadingData}
                  />
                  <StatCard
                    icon={<Dice5 size={20} className="text-violet-400" />}
                    label="Loss Pool"
                    value={`${fmt(poolSize)} FLR`}
                    loading={loadingData}
                  />
                </motion.div>

                {/* Two-column: Stake / Cashout */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                  {/* Stake Panel */}
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                    className="p-6 rounded-2xl bg-slate-900/60 backdrop-blur-sm border border-slate-800/50"
                  >
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <ArrowDownToLine size={18} className="text-violet-400" />
                      Stake
                    </h2>
                    {stakeData?.isStaked ? (
                      <div className="space-y-4">
                        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                          <p className="text-emerald-400 text-sm font-medium">Agent is staked</p>
                          <p className="text-white text-xl font-bold mt-1">{fmt(stakeData.stakedAmount)} FLR</p>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <Info size={12} />
                          Agent must be Inactive in registry to unstake
                        </div>
                        <button
                          onClick={doUnstake}
                          disabled={txPending || selectedAgentInfo?.isActive}
                          className="w-full px-4 py-2.5 rounded-xl border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                          <ArrowUpFromLine size={16} />
                          {selectedAgentInfo?.isActive ? "Agent Still Active" : "Unstake"}
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm text-slate-400 mb-1">
                            Amount (min {fmt(minStake)} FLR)
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="number"
                              value={stakeAmount}
                              onChange={(e) => setStakeAmount(e.target.value)}
                              placeholder={fmt(minStake)}
                              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700/50 text-white focus:outline-none focus:border-violet-500 transition-colors"
                            />
                            <button
                              onClick={doStake}
                              disabled={txPending || !selectedAgentInfo?.isActive}
                              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2"
                            >
                              {txPending ? <Loader2 size={16} className="animate-spin" /> : <ArrowDownToLine size={16} />}
                              Stake
                            </button>
                          </div>
                        </div>
                        {!selectedAgentInfo?.isActive && (
                          <p className="text-xs text-amber-400/70">Agent must be Active in registry to stake</p>
                        )}
                      </div>
                    )}
                  </motion.div>

                  {/* Cashout Gamble Panel */}
                  <motion.div
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                    className="p-6 rounded-2xl bg-slate-900/60 backdrop-blur-sm border border-slate-800/50"
                  >
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <Dice5 size={18} className="text-amber-400" />
                      Cashout Gamble
                    </h2>

                    {stakeData?.isStaked && preview && preview.earnings > 0n ? (
                      <div className="space-y-4">
                        {/* Preview */}
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-slate-400">Earnings</span>
                            <span className="text-white">{fmt(preview.earnings)} FLR</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">House Fee ({Number(houseFeeBps) / 100}%)</span>
                            <span className="text-red-400">-{fmt(preview.houseFee)} FLR</span>
                          </div>
                          <div className="border-t border-slate-700/50 pt-2 flex justify-between">
                            <span className="text-slate-400">Net Earnings</span>
                            <span className="text-white font-medium">
                              {fmt(preview.earnings - preview.houseFee)} FLR
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-emerald-400">Max Win (2x)</span>
                            <span className="text-emerald-400 font-bold">{fmt(preview.maxPayout)} FLR</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-red-400">If Lose</span>
                            <span className="text-red-400">0 FLR</span>
                          </div>
                        </div>

                        {/* Gamble Button */}
                        <button
                          onClick={doCashout}
                          disabled={txPending}
                          className="relative w-full py-4 rounded-2xl bg-gradient-to-r from-amber-600 via-orange-600 to-red-600 hover:from-amber-500 hover:via-orange-500 hover:to-red-500 text-white font-bold text-lg transition-all disabled:opacity-50 overflow-hidden group"
                        >
                          {gambleAnimating ? (
                            <span className="flex items-center justify-center gap-2">
                              <Loader2 size={20} className="animate-spin" />
                              Rolling...
                            </span>
                          ) : (
                            <span className="flex items-center justify-center gap-2">
                              <Dice5 size={20} />
                              GAMBLE CASHOUT
                            </span>
                          )}
                          <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/10 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
                        </button>
                        <p className="text-center text-xs text-slate-500">
                          50/50 powered by Flare RandomNumberV2
                        </p>

                        {/* Divider */}
                        <div className="flex items-center gap-3 pt-2">
                          <div className="flex-1 border-t border-slate-700/50" />
                          <span className="text-xs text-slate-500">or play it safe</span>
                          <div className="flex-1 border-t border-slate-700/50" />
                        </div>

                        {/* Safe Withdraw Preview */}
                        {safePreview && (
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-slate-400">Safe Fee ({Number(safeWithdrawFeeBps) / 100}%)</span>
                              <span className="text-red-400">-{fmt(safePreview.fee)} FLR</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-emerald-400">Guaranteed Payout</span>
                              <span className="text-emerald-400 font-bold">{fmt(safePreview.payout)} FLR</span>
                            </div>
                          </div>
                        )}

                        {/* Safe Withdraw Button */}
                        <button
                          onClick={doSafeWithdraw}
                          disabled={txPending}
                          className="w-full py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-base transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                          {txPending && !gambleAnimating ? (
                            <Loader2 size={18} className="animate-spin" />
                          ) : (
                            <Wallet size={18} />
                          )}
                          SAFE WITHDRAW ({100 - Number(safeWithdrawFeeBps) / 100}%)
                        </button>
                        <p className="text-center text-xs text-slate-500">
                          No gamble -- keep {100 - Number(safeWithdrawFeeBps) / 100}%, house takes {Number(safeWithdrawFeeBps) / 100}%
                        </p>

                        {/* Win/Loss Record */}
                        <div className="flex justify-center gap-6 text-sm">
                          <span className="flex items-center gap-1 text-emerald-400">
                            <Trophy size={14} /> {stakeData.wins.toString()}W
                          </span>
                          <span className="flex items-center gap-1 text-red-400">
                            <XCircle size={14} /> {stakeData.losses.toString()}L
                          </span>
                        </div>
                      </div>
                    ) : stakeData?.isStaked ? (
                      <div className="text-center py-6">
                        <p className="text-slate-500">No earnings to cash out yet.</p>
                        <p className="text-xs text-slate-600 mt-2">Earnings accrue from completed jobs via escrow.</p>
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <p className="text-slate-500">Stake your agent first to start earning.</p>
                      </div>
                    )}
                  </motion.div>
                </div>

                {/* Gamble Result Overlay */}
                <AnimatePresence>
                  {gambleAnimating && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
                    >
                      <motion.div
                        animate={{ rotate: [0, 360], scale: [1, 1.2, 1] }}
                        transition={{ duration: 1, repeat: Infinity }}
                        className="w-24 h-24 rounded-3xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-2xl shadow-amber-500/40"
                      >
                        <Dice5 size={48} className="text-white" />
                      </motion.div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {gambleResult && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
                      onClick={() => setGambleResult(null)}
                    >
                      <motion.div
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.5, opacity: 0 }}
                        className={`p-10 rounded-3xl border-2 text-center max-w-sm mx-4 ${
                          gambleResult.type === "win"
                            ? "bg-emerald-950/90 border-emerald-500/50 shadow-2xl shadow-emerald-500/30"
                            : "bg-red-950/90 border-red-500/50 shadow-2xl shadow-red-500/30"
                        }`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {gambleResult.type === "win" ? (
                          <>
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: [0, 1.3, 1] }}
                              transition={{ delay: 0.2, duration: 0.5 }}
                            >
                              <Trophy size={64} className="text-emerald-400 mx-auto mb-4" />
                            </motion.div>
                            <h3 className="text-3xl font-black text-emerald-400 mb-2">YOU WIN!</h3>
                            <p className="text-white text-xl font-bold">{fmt(gambleResult.payout)} FLR</p>
                            <p className="text-emerald-400/70 text-sm mt-2">Payout sent to your wallet</p>
                          </>
                        ) : (
                          <>
                            <motion.div
                              initial={{ x: 0 }}
                              animate={{ x: [-10, 10, -10, 10, 0] }}
                              transition={{ delay: 0.2, duration: 0.5 }}
                            >
                              <XCircle size={64} className="text-red-400 mx-auto mb-4" />
                            </motion.div>
                            <h3 className="text-3xl font-black text-red-400 mb-2">YOU LOSE</h3>
                            <p className="text-white text-xl font-bold">{fmt(gambleResult.lost)} FLR</p>
                            <p className="text-red-400/70 text-sm mt-2">Earnings added to loss pool</p>
                          </>
                        )}
                        <button
                          onClick={() => setGambleResult(null)}
                          className="mt-6 px-6 py-2 rounded-xl border border-slate-600 text-slate-300 hover:text-white hover:border-slate-400 transition-all text-sm"
                        >
                          Close
                        </button>
                      </motion.div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Contract Links */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/30"
                >
                  <h3 className="text-sm font-medium text-slate-400 mb-3">Contracts on Coston2</h3>
                  <div className="flex flex-wrap gap-3">
                    {[
                      { name: "AgentStaking", addr: CONTRACT_ADDRESSES.AgentStaking },
                      { name: "AgentRegistry", addr: CONTRACT_ADDRESSES.AgentRegistry },
                      { name: "RandomNumberV2", addr: CONTRACT_ADDRESSES.RandomNumberV2 },
                      { name: "FlareEscrow", addr: CONTRACT_ADDRESSES.FlareEscrow },
                    ].map((c) => (
                      <a
                        key={c.name}
                        href={explorerAddress(c.addr)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/40 text-xs text-slate-300 hover:text-violet-400 hover:border-violet-500/30 transition-all"
                      >
                        {c.name}
                        <ExternalLink size={10} />
                      </a>
                    ))}
                  </div>
                </motion.div>

                {/* Refresh */}
                <div className="mt-6 flex justify-center">
                  <button
                    onClick={() => {
                      fetchAgents();
                      fetchStakeData();
                    }}
                    className="flex items-center gap-2 text-xs text-slate-500 hover:text-violet-400 transition-colors"
                  >
                    <RefreshCw size={12} />
                    Refresh data
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------- small components ----------

function StatCard({
  icon,
  label,
  value,
  loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  loading: boolean;
}) {
  return (
    <div className="p-4 rounded-2xl bg-slate-900/60 backdrop-blur-sm border border-slate-800/50">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      {loading ? (
        <div className="h-7 w-24 bg-slate-800/50 rounded animate-pulse mt-1" />
      ) : (
        <p className="text-xl font-bold text-white">{value}</p>
      )}
    </div>
  );
}

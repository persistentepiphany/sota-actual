"use client";

import { useState } from "react";
import { useAccount, useBalance, useDisconnect } from "wagmi";
import { motion, AnimatePresence } from "motion/react";
import { Copy, Check, ExternalLink, LogOut, Wallet, RefreshCw, Circle } from "lucide-react";
import { WalletConnectButton } from "./WalletConnectButton";
import { flareCoston2 } from "@/src/wagmiConfig";

const CHAIN_ID = flareCoston2.id;

export default function WalletScreen() {
  const { address, isConnected, connector } = useAccount();
  const { disconnect } = useDisconnect();
  const { data: balance, isLoading: balLoading, refetch: refetchBal } = useBalance({
    address,
    chainId: CHAIN_ID,
    query: { enabled: !!address && isConnected, refetchInterval: 12_000 },
  });

  const [copied, setCopied] = useState(false);

  const copyAddress = () => {
    if (!address) return;
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  /* ── Not connected ── */
  if (!isConnected) {
    return (
      <div className="wallet-screen">
        <h2 className="screen-title">Wallet</h2>

        <motion.div
          className="wallet-connect-prompt"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="wallet-connect-hero">
            <div className="wallet-connect-icon-ring">
              <Wallet size={32} />
            </div>
            <h3 className="wallet-connect-heading">Connect Your Wallet</h3>
            <p className="wallet-connect-sub">
              Link your wallet to view balances, sign transactions, and interact with SOTA Butler on Flare.
            </p>
          </div>

          <WalletConnectButton />

          <p className="wallet-connect-network">
            <Circle size={8} className="wallet-network-dot" />
            Flare Coston2 Testnet
          </p>
        </motion.div>
      </div>
    );
  }

  /* ── Connected ── */
  const balFormatted = balance
    ? `${Number(balance.formatted).toFixed(4)} ${balance.symbol}`
    : "—";

  const explorerUrl = `${flareCoston2.blockExplorers.default.url}/address/${address}`;

  return (
    <div className="wallet-screen">
      <h2 className="screen-title">Wallet</h2>

      {/* ── Connection status ── */}
      <motion.div
        className="glass-card wallet-status-card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="wallet-status-row">
          <div className="wallet-status-dot connected" />
          <span className="wallet-status-label">Connected via {connector?.name || 'Wallet'}</span>
        </div>
        <span className="wallet-status-network">Flare Coston2 Testnet</span>
      </motion.div>

      {/* ── Address card ── */}
      <motion.div
        className="glass-card wallet-address-card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
      >
        <span className="wallet-label">Address</span>
        <div className="wallet-address-row">
          <span className="wallet-address-full">{address}</span>
          <div className="wallet-address-actions">
            <button className="wallet-icon-btn" onClick={copyAddress} title="Copy address">
              <AnimatePresence mode="wait">
                {copied ? (
                  <motion.div key="check" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                    <Check size={14} className="text-green" />
                  </motion.div>
                ) : (
                  <motion.div key="copy" initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
                    <Copy size={14} />
                  </motion.div>
                )}
              </AnimatePresence>
            </button>
            <a
              href={explorerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="wallet-icon-btn"
              title="View on explorer"
            >
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </motion.div>

      {/* ── Balance card ── */}
      <motion.div
        className="glass-card wallet-balance-card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="wallet-balance-header">
          <span className="wallet-label">Native Balance</span>
          <button
            className="wallet-icon-btn"
            onClick={() => refetchBal()}
            title="Refresh balance"
          >
            <RefreshCw size={14} className={balLoading ? 'spinning' : ''} />
          </button>
        </div>
        <div className="wallet-balance-value">
          {balLoading ? (
            <span className="wallet-balance-loading">Loading…</span>
          ) : (
            <>
              <span className="wallet-balance-amount">{balFormatted}</span>
            </>
          )}
        </div>
      </motion.div>

      {/* ── Disconnect ── */}
      <motion.button
        className="disconnect-btn"
        onClick={() => disconnect()}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        whileTap={{ scale: 0.97 }}
      >
        <LogOut size={16} />
        <span>Disconnect Wallet</span>
      </motion.button>
    </div>
  );
}

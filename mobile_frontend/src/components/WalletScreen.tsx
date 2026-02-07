"use client";

import { useAccount, useBalance, useDisconnect } from "wagmi";
import { WalletConnectButton } from "./WalletConnectButton";
import { SendToButler } from "./SendToButler";
import UsdcBalance from "./UsdcBalance";

export default function WalletScreen() {
  const { address, isConnected } = useAccount();
  const { disconnect } = useDisconnect();
  const { data: flrBalance } = useBalance({ address });

  if (!isConnected) {
    return (
      <div className="wallet-screen">
        <h2 className="screen-title">Wallet</h2>
        <div className="wallet-connect-prompt">
          <p className="empty-state">Connect your wallet to get started.</p>
          <WalletConnectButton />
        </div>
      </div>
    );
  }

  return (
    <div className="wallet-screen">
      <h2 className="screen-title">Wallet</h2>

      {/* Address card */}
      <div className="glass-card wallet-address-card">
        <span className="wallet-label">Connected Address</span>
        <span className="wallet-address-full">{address}</span>
      </div>

      {/* Balance cards */}
      <div className="balance-grid">
        <div className="glass-card balance-card">
          <span className="balance-label">FLR Balance</span>
          <span className="balance-value">
            {flrBalance ? `${Number(flrBalance.formatted).toFixed(4)} FLR` : "—"}
          </span>
        </div>
        <div className="glass-card balance-card">
          <span className="balance-label">USDC Balance</span>
          <UsdcBalance />
        </div>
      </div>

      {/* Quick actions */}
      <div className="glass-card wallet-actions-card">
        <h3 className="card-subtitle">Quick Actions</h3>
        <SendToButler />
      </div>

      {/* Disconnect */}
      <button className="disconnect-btn" onClick={() => disconnect()}>
        Disconnect Wallet
      </button>
    </div>
  );
}

"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { useAccount, useConnect } from 'wagmi';
import { Wallet, Loader2, Plug, Download, ExternalLink } from 'lucide-react';

const isRequestResetError = (err: unknown) => {
  const message = (err as any)?.message || (err as any)?.toString?.() || '';
  return /connection request reset/i.test(message);
};

const isProviderMissing = (err: unknown) => {
  const message = (err as any)?.shortMessage || (err as any)?.message || (err as any)?.toString?.() || '';
  return /provider.*not found|no provider|provider.*unavailable/i.test(message);
};

/** Check if an injected EIP-1193 provider exists */
const hasInjectedProvider = () =>
  typeof window !== 'undefined' && typeof (window as any).ethereum !== 'undefined';

/** Connectors that require a browser extension */
const isInjectedType = (id: string) =>
  ['injected', 'io.metamask', 'metaMaskSDK', 'metaMask'].includes(id);

/** Friendly connector name */
const connectorLabel = (id: string, name: string) => {
  if (id === 'injected' || id === 'io.metamask') return 'Browser Wallet';
  if (id === 'walletConnect') return 'WalletConnect';
  if (id === 'metaMaskSDK' || id === 'metaMask') return 'MetaMask';
  if (id === 'coinbaseWalletSDK') return 'Coinbase';
  return name;
};

export const WalletConnectButton: React.FC = () => {
  const [mounted, setMounted] = useState(false);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { isConnected } = useAccount();
  const { connectors, connectAsync } = useConnect();

  useEffect(() => {
    setMounted(true);
    const suppress = (e: PromiseRejectionEvent) => {
      if (/connection request reset/i.test((e.reason?.message || e.reason || '').toString())) {
        e.preventDefault();
      }
    };
    window.addEventListener('unhandledrejection', suppress);
    return () => window.removeEventListener('unhandledrejection', suppress);
  }, []);

  const injectedAvailable = mounted && hasInjectedProvider();

  // Deduplicate and filter connectors
  const available = useMemo(() => {
    if (!mounted) return [];
    const seen = new Set<string>();
    return connectors.filter((c) => {
      const key = c.id;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [mounted, connectors]);

  const handleConnect = async (connector: typeof connectors[0]) => {
    // Guard: injected connector without window.ethereum
    if (isInjectedType(connector.id) && !hasInjectedProvider()) {
      setError('No browser wallet detected. Install MetaMask or open this page in a Web3 browser.');
      return;
    }

    setError(null);
    setConnectingId(connector.id);
    try {
      await connectAsync({ connector });
    } catch (err) {
      if (isRequestResetError(err)) return;
      const msg = (err as any)?.shortMessage || (err as any)?.message || 'Connection failed';
      if (/user rejected|user denied/i.test(msg)) {
        setError(null);
      } else if (isProviderMissing(err)) {
        setError('No browser wallet detected. Install MetaMask or open this page in a Web3 browser.');
      } else {
        setError(msg);
      }
    } finally {
      setConnectingId(null);
    }
  };

  if (isConnected || !mounted) return null;

  return (
    <div className="wallet-connect-options">
      {available.map((c) => {
        const isLoading = connectingId === c.id;
        const needsExtension = isInjectedType(c.id) && !injectedAvailable;

        return (
          <button
            key={c.id}
            type="button"
            className={`wallet-connect-btn${needsExtension ? ' wallet-connect-btn--dimmed' : ''}`}
            onClick={() => handleConnect(c)}
            disabled={!!connectingId}
          >
            {isLoading ? (
              <Loader2 size={18} className="wallet-connect-btn-icon spinning" />
            ) : needsExtension ? (
              <Download size={18} className="wallet-connect-btn-icon" />
            ) : (
              <Plug size={18} className="wallet-connect-btn-icon" />
            )}
            <span>
              {isLoading
                ? 'Connecting…'
                : needsExtension
                  ? `${connectorLabel(c.id, c.name)} (not detected)`
                  : connectorLabel(c.id, c.name)}
            </span>
          </button>
        );
      })}

      {/* Install MetaMask CTA when no injected provider */}
      {!injectedAvailable && (
        <a
          href="https://metamask.io/download/"
          target="_blank"
          rel="noopener noreferrer"
          className="wallet-install-link"
        >
          <Download size={16} />
          <span>Install MetaMask</span>
          <ExternalLink size={12} />
        </a>
      )}

      {error && (
        <p className="wallet-connect-error">{error}</p>
      )}
    </div>
  );
};

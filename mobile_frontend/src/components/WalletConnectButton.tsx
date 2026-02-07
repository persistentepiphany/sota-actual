"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { useAccount, useConnect } from 'wagmi';
import { Loader2, Plug, Download, ExternalLink, Smartphone, Monitor, QrCode } from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────

const isRequestResetError = (err: unknown) => {
  const msg = (err as any)?.message || (err as any)?.toString?.() || '';
  return /connection request reset/i.test(msg);
};

const isProviderMissing = (err: unknown) => {
  const msg = (err as any)?.shortMessage || (err as any)?.message || '';
  return /provider.*not found|no provider|provider.*unavailable/i.test(msg);
};

const hasInjectedProvider = () =>
  typeof window !== 'undefined' && typeof (window as any).ethereum !== 'undefined';

const isMobileDevice = () => {
  if (typeof navigator === 'undefined') return false;
  return /Mobi|Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent
  );
};

const isInjectedType = (id: string) =>
  ['injected', 'io.metamask', 'metaMaskSDK', 'metaMask'].includes(id);

const connectorLabel = (id: string, name: string) => {
  if (id === 'walletConnect') return 'WalletConnect';
  if (id === 'injected' || id === 'io.metamask') return 'Browser Wallet';
  if (id === 'metaMaskSDK' || id === 'metaMask') return 'MetaMask';
  if (id === 'coinbaseWalletSDK') return 'Coinbase Wallet';
  return name;
};

const connectorIcon = (id: string, isMobile: boolean) => {
  if (id === 'walletConnect')
    return isMobile ? <Smartphone size={18} /> : <QrCode size={18} />;
  if (id === 'coinbaseWalletSDK')
    return <Plug size={18} />;
  return <Monitor size={18} />;
};

const connectorSubtitle = (id: string, isMobile: boolean) => {
  if (id === 'walletConnect')
    return isMobile ? 'Opens your wallet app' : 'Scan QR code with your phone';
  if (id === 'coinbaseWalletSDK')
    return 'Coinbase Wallet app or extension';
  return 'MetaMask, Rabby, or other extension';
};

// ── Component ────────────────────────────────────────────────

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

  const mobile = mounted && isMobileDevice();
  const injectedAvailable = mounted && hasInjectedProvider();

  // Deduplicate, filter, and sort connectors by device type
  const available = useMemo(() => {
    if (!mounted) return [];
    const seen = new Set<string>();

    const filtered = connectors.filter((c) => {
      if (seen.has(c.id)) return false;
      seen.add(c.id);
      // On mobile: hide injected (no browser extensions on phones)
      if (mobile && isInjectedType(c.id) && !injectedAvailable) return false;
      // On desktop: hide injected only if no extension detected
      if (!mobile && isInjectedType(c.id) && !injectedAvailable) return false;
      return true;
    });

    // Sort: WalletConnect first on mobile, injected first on desktop
    return filtered.sort((a, b) => {
      if (mobile) {
        if (a.id === 'walletConnect') return -1;
        if (b.id === 'walletConnect') return 1;
      } else {
        if (isInjectedType(a.id)) return -1;
        if (isInjectedType(b.id)) return 1;
        if (a.id === 'walletConnect') return -1;
        if (b.id === 'walletConnect') return 1;
      }
      return 0;
    });
  }, [mounted, connectors, mobile, injectedAvailable]);

  const handleConnect = async (connector: typeof connectors[0]) => {
    if (isInjectedType(connector.id) && !hasInjectedProvider()) {
      setError('No browser wallet detected. Install MetaMask or use WalletConnect / Coinbase.');
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
        setError('No browser wallet detected. Use WalletConnect or Coinbase Wallet instead.');
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
      {/* Device mode indicator */}
      <div className="wallet-device-hint">
        {mobile ? (
          <><Smartphone size={14} /> <span>Mobile — tap to open wallet app</span></>
        ) : (
          <><Monitor size={14} /> <span>Desktop — scan QR or use extension</span></>
        )}
      </div>

      {available.map((c) => {
        const isLoading = connectingId === c.id;
        const isPrimary = mobile ? c.id === 'walletConnect' : isInjectedType(c.id);

        return (
          <button
            key={c.id}
            type="button"
            className={`wallet-connect-btn${isPrimary ? ' wallet-connect-btn--primary' : ''}`}
            onClick={() => handleConnect(c)}
            disabled={!!connectingId}
          >
            <span className="wallet-connect-btn-icon">
              {isLoading ? (
                <Loader2 size={18} className="spinning" />
              ) : (
                connectorIcon(c.id, mobile)
              )}
            </span>
            <span className="wallet-connect-btn-text">
              <span className="wallet-connect-btn-label">
                {isLoading ? 'Connecting…' : connectorLabel(c.id, c.name)}
              </span>
              <span className="wallet-connect-btn-sub">
                {connectorSubtitle(c.id, mobile)}
              </span>
            </span>
          </button>
        );
      })}

      {/* MetaMask install link on desktop when no injected provider */}
      {!mobile && !injectedAvailable && (
        <a
          href="https://metamask.io/download/"
          target="_blank"
          rel="noopener noreferrer"
          className="wallet-install-link"
        >
          <Download size={16} />
          <span>Install MetaMask browser extension</span>
          <ExternalLink size={12} />
        </a>
      )}

      {error && (
        <p className="wallet-connect-error">{error}</p>
      )}
    </div>
  );
};

"use client";

import React, { useEffect, useMemo, useState } from 'react';
import { useAccount, useConnect, useDisconnect, useBalance } from 'wagmi';
import { formatUnits } from 'viem';

const FLARE_COSTON2_ID = 114;

const truncateAddress = (address: string) => {
  if (!address) return '';
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
};

const isRequestResetError = (err: unknown) => {
  const message = (err as any)?.message || (err as any)?.toString?.() || '';
  return /connection request reset/i.test(message);
};

/** Detect mobile via user-agent */
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const ua = navigator.userAgent || '';
    setIsMobile(/iPhone|iPad|iPod|Android|webOS|BlackBerry|IEMobile|Opera Mini/i.test(ua));
  }, []);
  return isMobile;
};

export const WalletConnectButton: React.FC = () => {
  const [mounted, setMounted] = useState(false);
  const isMobile = useIsMobile();
  const { address, isConnected, status: accountStatus } = useAccount();
  const { connectors, connectAsync, status: connectStatus } = useConnect({
    mutation: {
      onError: (err) => {
        if (isRequestResetError(err)) {
          console.info('walletconnect pairing cancelled/reset');
          return;
        }
        console.error('wallet connect error', err);
      },
    },
  });
  const { disconnect } = useDisconnect();

  // Native FLR balance on Flare Coston2
  const { data: balanceData, isLoading: isBalLoading } = useBalance({
    address: address,
    chainId: FLARE_COSTON2_ID,
    query: {
      enabled: !!address && isConnected,
      refetchInterval: 15000,
    },
  });

  useEffect(() => {
    setMounted(true);
    const suppressReset = (event: PromiseRejectionEvent) => {
      const message = (event.reason?.message || event.reason || '').toString();
      if (/connection request reset/i.test(message)) {
        event.preventDefault();
        console.info('walletconnect pairing cancelled/reset');
      }
    };
    window.addEventListener('unhandledrejection', suppressReset);
    return () => {
      window.removeEventListener('unhandledrejection', suppressReset);
    };
  }, []);

  const isConnecting = connectStatus === 'pending';

  // Device-aware connector selection:
  //   Desktop → WalletConnect (shows QR code modal)
  //   Mobile  → Injected (deep-links to wallet app) → fallback to WalletConnect
  const primaryConnector = useMemo(() => {
    if (!mounted) return undefined;

    const injected = connectors.find(
      (c) => c.type === 'injected' && typeof window !== 'undefined' && !!(window as any).ethereum
    );
    const wc = connectors.find((c) => c.id === 'walletConnect');
    const mm = connectors.find((c) => c.id === 'metaMask');

    if (isMobile) {
      // Mobile: prefer injected (in-app browser) → WalletConnect deep-link → MetaMask
      return injected || wc || mm || connectors[0];
    }

    // Desktop: prefer WalletConnect (shows QR modal) → injected → MetaMask
    return wc || injected || mm || connectors[0];
  }, [mounted, connectors, isMobile]);

  const disabled = !mounted || !primaryConnector || isConnecting || accountStatus === 'connecting';

  const label = useMemo(() => {
    if (isConnecting) return 'Connecting…';
    if (isMobile) return 'Connect Wallet';
    return '🔗 Scan QR to Connect';
  }, [isConnecting, isMobile]);

  const handleConnect = async () => {
    if (!primaryConnector) return;
    try {
      await connectAsync({ connector: primaryConnector });
    } catch (err) {
      if (isRequestResetError(err)) {
        console.info('walletconnect pairing cancelled/reset');
        return;
      }
      console.info('connect cancelled or failed', err);
    }
  };

  const balanceDisplay = useMemo(() => {
    if (!isConnected || !address) return null;
    if (isBalLoading) return '…';
    if (!balanceData) return '—';
    const num = Number.parseFloat(formatUnits(balanceData.value, balanceData.decimals));
    return `${num.toFixed(2)} C2FLR`;
  }, [isConnected, address, isBalLoading, balanceData]);

  if (isConnected && mounted) {
    return (
      <div className="wallet-chip">
        <div className="token-pill">
          <div className="token-icon">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v12M6 12h12" />
            </svg>
          </div>
          <div className="token-text">
            <span className="token-label">{truncateAddress(address!)}</span>
            <span className="token-amount">{balanceDisplay}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => disconnect()}
          className="btn-secondary wallet-disconnect"
          aria-label="Disconnect wallet"
        >
          <svg className="icon-exit" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M5 4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v4h-2V4H7v16h6v-4h2v4a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4Zm13.707 7.293a1 1 0 0 1 0 1.414l-3 3a1 1 0 0 1-1.414-1.414L15.586 13H10v-2h5.586l-1.293-1.293a1 1 0 1 1 1.414-1.414l3 3Z"
            />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="wallet-chip">
      <button
        type="button"
        className="btn-primary wallet-connect"
        onClick={handleConnect}
        disabled={disabled}
      >
        {label}
      </button>
    </div>
  );
};

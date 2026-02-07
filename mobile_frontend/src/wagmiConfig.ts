import { http, createConfig } from 'wagmi';
import { injected, walletConnect, coinbaseWallet } from 'wagmi/connectors';
import { defineChain } from 'viem';

export const flareCoston2 = defineChain({
  id: 114,
  name: 'Flare Coston2 Testnet',
  nativeCurrency: { name: 'Coston2 Flare', symbol: 'C2FLR', decimals: 18 },
  rpcUrls: {
    default: {
      http: [process.env.NEXT_PUBLIC_FLARE_RPC_URL || 'https://coston2-api.flare.network/ext/C/rpc'],
    },
  },
  blockExplorers: {
    default: {
      name: 'Flare Coston2 Explorer',
      url: 'https://coston2-explorer.flare.network',
    },
  },
  testnet: true,
});

// ── WalletConnect project ID ────────────────────────────────
// Get one free at https://cloud.walletconnect.com
const WC_PROJECT_ID =
  process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || 'demo-project-id';

// ── Build connectors ────────────────────────────────────────
const hasRealWcId = WC_PROJECT_ID !== 'demo-project-id';

const connectors = (() => {
  const list: ReturnType<typeof injected>[] = [];

  // 1. Browser-injected wallet (MetaMask, Rabby, etc.)
  list.push(injected({ shimDisconnect: true }));

  // 2. WalletConnect — only if we have a real project ID
  if (hasRealWcId) {
    list.push(
      walletConnect({
        projectId: WC_PROJECT_ID,
        metadata: {
          name: 'SOTA Butler',
          description: 'AI Agent Marketplace on Flare',
          url: typeof window !== 'undefined' ? window.location.origin : 'https://sota.app',
          icons: ['https://walletconnect.com/walletconnect-logo.png'],
        },
        showQrModal: true,
      }) as any
    );
  }

  // 3. Coinbase Wallet — works without WC project ID
  list.push(
    coinbaseWallet({
      appName: 'SOTA Butler',
    }) as any
  );

  return list;
})();

export const wagmiConfig = createConfig({
  chains: [flareCoston2],
  transports: {
    [flareCoston2.id]: http(flareCoston2.rpcUrls.default.http[0]),
  },
  connectors,
  ssr: true,
});

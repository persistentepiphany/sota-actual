import { http, createConfig, createConnector } from 'wagmi';
import { injected, walletConnect } from 'wagmi/connectors';
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

// Build connectors list — WalletConnect only if project ID is provided
const connectors = (() => {
  const list = [
    injected({ shimDisconnect: true }),
  ];

  const wcProjectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID;
  if (wcProjectId) {
    list.push(
      walletConnect({
        projectId: wcProjectId,
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

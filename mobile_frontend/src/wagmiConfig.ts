import { http, createConfig } from 'wagmi';
import { injected, metaMask, coinbaseWallet, walletConnect } from 'wagmi/connectors';

const flareCoston2 = {
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
} as const;

export const wagmiConfig = createConfig({
  chains: [flareCoston2],
  transports: {
    [flareCoston2.id]: http(flareCoston2.rpcUrls.default.http[0]),
  },
  connectors: [
    injected({ shimDisconnect: true }),
    metaMask({ shimDisconnect: true }),
    coinbaseWallet({ appName: 'SOTA Butler' }),
    walletConnect({
      projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || '',
      metadata: {
        name: 'SOTA Butler',
        description: 'AI Agent Marketplace on Flare',
        url: 'https://example.com',
        icons: ['https://walletconnect.com/walletconnect-logo.png'],
      },
      showQrModal: true,
    }),
  ],
  ssr: true,
});

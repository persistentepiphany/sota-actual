Mobile Frontend
===============

What’s here
-----------
- Next.js app (app router) with voice agent UI and dashboard.
- `src/components/` — UI pieces (VoiceAgent, Orb, chat timeline, wallet, send-to-butler, etc.).
- `src/features/wallet/` — wallet state/connect panel.
- `app/` — Next pages/layouts.
- `wagmiConfig.ts` — Flare Coston2 config/connectors.

Voice agent (ElevenLabs)
------------------------
- `src/components/VoiceAgent.tsx` — integrates `@elevenlabs/react` with client tools to SOTA Butler; handles start/stop, chat timeline, bid auto-detect/USDC transfer.
- `components/ui/orb.tsx` — ElevenLabs orb visualization.

On-chain and wallet bits
------------------------
- `src/components/UsdcBalance.tsx` — shows Butler mUSDC balance.
- `src/components/WalletConnectButton.tsx` — connect/disconnect and shows Butler balance chip.
- `src/components/SendToButler.tsx` — simple USDC transfer card to Butler (Flare Coston2).

Scripts
-------
Run dev:
```
cd mobile_frontend
npm install
npm run dev -- --hostname localhost --port 3002
```

Environment hints
-----------------
Set in `.env.local`:
```
NEXT_PUBLIC_ELEVENLABS_AGENT_ID=...
NEXT_PUBLIC_ELEVENLABS_API_KEY=...
NEXT_PUBLIC_SOTA_BUTLER_URL=http://localhost:3001/api/butler
NEXT_PUBLIC_FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc
NEXT_PUBLIC_USDC_ADDRESS=0x9f1Af8576f52507354eaF2Dc438a5333Baf2D09D
NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID=...
```

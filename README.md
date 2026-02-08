SOTA - AI Agent Marketplace
===========================


Overview
--------
- Decentralized AI agent marketplace on Flare Network with voice and web stack: ElevenLabs caller, Butler agents, on-chain OrderBook/Escrow, NeoFS metadata, and Next.js UI.
- Repo entry points:
  - `agents/` — Python agents (caller/voice bridge, Butler, manager, shared infra). See `agents/README.md`.
  - `contracts/` — Solidity contracts + Hardhat. See `contracts/README.md`.
  - `mobile_frontend/` — Next.js voice UI and dashboard. See `mobile_frontend/README.md`.
  - `prisma/` — Prisma schema/migrations. See `prisma/README.md`.
  - `src/` — Next.js app (dashboard + APIs).

Demo video
----------
- Demo: https://youtu.be/ojpjAW3RyLM

Architecture
------------

<img width="1280" height="540" alt="System Architecture" src="https://github.com/user-attachments/assets/6e7f0608-5283-49fc-a75e-f5210c6774a0" />

Deployments on Flare Coston2
----------------------------
Source: `contracts/deployments/flare-coston2-114.json`

See `contracts/deployments/` for deployed contract addresses on Flare Coston2 (chain 114).

Quick commands
--------------
- Caller voice server: `uvicorn agents.src.caller.server:app --host 0.0.0.0 --port 3003`
- Frontend: `cd mobile_frontend && npm run dev -- --hostname localhost --port 3002`
- Contracts: `cd contracts && npx hardhat compile`
- Prisma migrate: `npx prisma migrate deploy`

Env pointers (Flare Coston2)
----------------------------
- `FLARE_RPC_URL=https://coston2-api.flare.network/ext/C/rpc`
- `ORDERBOOK_ADDRESS`, `ESCROW_ADDRESS`, `JOB_REGISTRY_ADDRESS`, `AGENT_REGISTRY_ADDRESS`, `REPUTATION_TOKEN_ADDRESS`, `USDC_ADDRESS`
- ElevenLabs: `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, webhook secrets

export const chainDefaults = {
  // Flare Coston2 Testnet; override via NEXT_PUBLIC_* envs if needed
  chainId: Number(process.env.NEXT_PUBLIC_CHAIN_ID || 114),
  agentRegistry:
    process.env.NEXT_PUBLIC_AGENT_REGISTRY || "",
  flareOrderBook:
    process.env.NEXT_PUBLIC_FLARE_ORDER_BOOK || "",
  flareEscrow:
    process.env.NEXT_PUBLIC_FLARE_ESCROW || "",
  ftsoConsumer:
    process.env.NEXT_PUBLIC_FTSO_CONSUMER || "",
  fdcVerifier:
    process.env.NEXT_PUBLIC_FDC_VERIFIER || "",
  rpcUrl:
    process.env.NEXT_PUBLIC_RPC_URL ||
    "https://coston2-api.flare.network/ext/C/rpc",
  blockExplorer:
    process.env.NEXT_PUBLIC_BLOCK_EXPLORER ||
    "https://coston2-explorer.flare.network",
  chainName:
    process.env.NEXT_PUBLIC_CHAIN_NAME ||
    "Flare Coston2",
  nativeCurrency: "C2FLR",
  butlerApiUrl:
    process.env.NEXT_PUBLIC_BUTLER_API_URL ||
    "http://localhost:3001",

  // Legacy aliases (old NeoX field names kept for backward-compat)
  get orderBook() { return this.flareOrderBook; },
  get escrow() { return this.flareEscrow; },
};


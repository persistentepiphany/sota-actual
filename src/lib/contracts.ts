// Flare Coston2 testnet chain config & contract ABIs for frontend use

export const COSTON2_CHAIN = {
  id: 114,
  name: "Flare Coston2",
  rpcUrl: "https://coston2-api.flare.network/ext/C/rpc",
  explorer: "https://coston2-explorer.flare.network",
  nativeCurrency: { name: "Coston2 FLR", symbol: "C2FLR", decimals: 18 },
} as const;

export const CONTRACT_ADDRESSES = {
  AgentStaking: "0x695637E3B93Ce57F587290933300Bfa1a307204A" as `0x${string}`,
  AgentRegistry: "0x861a98D0725Df0E3afb909E046c88a71f501fB62" as `0x${string}`,
  RandomNumberV2: "0x5CdF9eAF3EB8b44fB696984a1420B56A7575D250" as `0x${string}`,
  FlareOrderBook: "0x9c065aFAB518DebA9704041092d3FF1B6415aF09" as `0x${string}`,
  FlareEscrow: "0x721F0259f3336336921f4EE1Ad5fe28C54Be6De7" as `0x${string}`,
} as const;

export function explorerAddress(addr: string) {
  return `${COSTON2_CHAIN.explorer}/address/${addr}`;
}

export function explorerTx(hash: string) {
  return `${COSTON2_CHAIN.explorer}/tx/${hash}`;
}

// Minimal ABIs — only the functions/events the frontend needs

export const AGENT_STAKING_ABI = [
  // Views
  {
    type: "function",
    name: "getStakeInfo",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [
      {
        name: "",
        type: "tuple",
        components: [
          { name: "stakedAmount", type: "uint256" },
          { name: "accumulatedEarnings", type: "uint256" },
          { name: "wins", type: "uint256" },
          { name: "losses", type: "uint256" },
          { name: "isStaked", type: "bool" },
        ],
      },
    ],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "previewCashout",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [
      { name: "earnings", type: "uint256" },
      { name: "houseFee", type: "uint256" },
      { name: "maxPayout", type: "uint256" },
    ],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "getPoolSize",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "minimumStake",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "houseFeeBps",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "isStaked",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [{ name: "", type: "bool" }],
    stateMutability: "view",
  },
  // Writes
  {
    type: "function",
    name: "stake",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [],
    stateMutability: "payable",
  },
  {
    type: "function",
    name: "cashout",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [],
    stateMutability: "nonpayable",
  },
  {
    type: "function",
    name: "unstake",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [],
    stateMutability: "nonpayable",
  },
  // Events
  {
    type: "event",
    name: "Staked",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "amount", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "CashoutWin",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "payout", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "CashoutLoss",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "lostEarnings", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "Unstaked",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "amount", type: "uint256", indexed: false },
      { name: "forfeitedEarnings", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "EarningsCredited",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "amount", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "HouseFeePaid",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "amount", type: "uint256", indexed: false },
    ],
  },
] as const;

export const AGENT_REGISTRY_ABI = [
  {
    type: "function",
    name: "getDeveloper",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [{ name: "", type: "address" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "isAgentActive",
    inputs: [{ name: "wallet", type: "address" }],
    outputs: [{ name: "", type: "bool" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "getAgent",
    inputs: [{ name: "wallet", type: "address" }],
    outputs: [
      {
        name: "",
        type: "tuple",
        components: [
          { name: "developer", type: "address" },
          { name: "name", type: "string" },
          { name: "metadataURI", type: "string" },
          { name: "capabilities", type: "string[]" },
          { name: "reputation", type: "uint256" },
          { name: "status", type: "uint8" },
          { name: "createdAt", type: "uint256" },
          { name: "updatedAt", type: "uint256" },
        ],
      },
    ],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "agentCount",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "getAllAgents",
    inputs: [],
    outputs: [
      {
        name: "list",
        type: "tuple[]",
        components: [
          { name: "developer", type: "address" },
          { name: "name", type: "string" },
          { name: "metadataURI", type: "string" },
          { name: "capabilities", type: "string[]" },
          { name: "reputation", type: "uint256" },
          { name: "status", type: "uint8" },
          { name: "createdAt", type: "uint256" },
          { name: "updatedAt", type: "uint256" },
        ],
      },
    ],
    stateMutability: "view",
  },
] as const;

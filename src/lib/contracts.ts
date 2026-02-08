// Flare Coston2 testnet chain config & contract ABIs for frontend use

export const COSTON2_CHAIN = {
  id: 114,
  name: "Flare Coston2",
  rpcUrl: "https://coston2-api.flare.network/ext/C/rpc",
  explorer: "https://coston2-explorer.flare.network",
  nativeCurrency: { name: "Coston2 FLR", symbol: "C2FLR", decimals: 18 },
} as const;

export const CONTRACT_ADDRESSES = {
  AgentStaking: "0x337562BE508c551B62385E9cdABa4C3EA685E360" as `0x${string}`,
  AgentRegistry: "0x46aDDBd334de452746443798d32C7C7C5fC8Dd16" as `0x${string}`,
  RandomNumberV2: "0x5CdF9eAF3EB8b44fB696984a1420B56A7575D250" as `0x${string}`,
  FlareOrderBook: "0x390413F0c7826523403760E086775DA9004aD004" as `0x${string}`,
  FlareEscrow: "0xA961AA0d21C2F24a20B6bdAD683f1DaFA45CFc73" as `0x${string}`,
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
    name: "safeWithdrawFeeBps",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "previewSafeWithdraw",
    inputs: [{ name: "agent", type: "address" }],
    outputs: [
      { name: "earnings", type: "uint256" },
      { name: "fee", type: "uint256" },
      { name: "payout", type: "uint256" },
    ],
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
  {
    type: "function",
    name: "safeWithdraw",
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
  {
    type: "event",
    name: "SafeWithdraw",
    inputs: [
      { name: "agent", type: "address", indexed: true },
      { name: "payout", type: "uint256", indexed: false },
      { name: "fee", type: "uint256", indexed: false },
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

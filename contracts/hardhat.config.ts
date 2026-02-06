import { config as dotenvConfig } from "dotenv";
import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

dotenvConfig();

const flareAccounts = process.env.FLARE_PRIVATE_KEY
  ? [process.env.FLARE_PRIVATE_KEY]
  : [];

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  defaultNetwork: "hardhat",
  networks: {
    hardhat: {
      chainId: 31337,
    },

    // ─── Flare Networks ───────────────────────────────────
    flareCoston2: {
      url: process.env.FLARE_RPC_URL || "https://coston2-api.flare.network/ext/C/rpc",
      chainId: 114,
      accounts: flareAccounts,
    },
    flareMainnet: {
      url: "https://flare-api.flare.network/ext/C/rpc",
      chainId: 14,
      accounts: flareAccounts,
    },

    // ─── Legacy Networks (kept for reference) ─────────────
    neoxTestnet: {
      url: process.env.NEOX_RPC_URL || "https://testnet.rpc.banelabs.org",
      chainId: 12227332,
      accounts: process.env.NEOX_PRIVATE_KEY ? [process.env.NEOX_PRIVATE_KEY] : [],
      gasPrice: 40_000_000_000,
    },
  },
};

export default config;

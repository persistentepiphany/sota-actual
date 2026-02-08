/**
 * End-to-end test of staking + cashout on Coston2 live network.
 *
 * Flow:
 *   1. Register a test agent in AgentRegistry
 *   2. Stake FLR for that agent
 *   3. Credit earnings (temporarily set escrow to deployer)
 *   4. Preview cashout
 *   5. Cashout (50/50 gamble via RandomNumberV2)
 *   6. Show result
 *   7. Unstake
 *
 * Usage:
 *   npx hardhat run scripts/test-staking-flow.ts --network flareCoston2
 */
import { config as dotenvConfig } from "dotenv";
import { ethers } from "hardhat";
import path from "path";

dotenvConfig({ path: path.resolve(__dirname, "..", "..", ".env") });

const ADDRESSES = {
  AgentRegistry: "0x46aDDBd334de452746443798d32C7C7C5fC8Dd16",
  AgentStaking: "0xD381Bf340de5E4b9b16e382913121B6E2fA1E6Af",
  FlareEscrow: "0xA961AA0d21C2F24a20B6bdAD683f1DaFA45CFc73",
  RandomNumberV2: "0x5CdF9eAF3EB8b44fB696984a1420B56A7575D250",
};

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  const [deployer] = await ethers.getSigners();
  const balance = await deployer.provider!.getBalance(deployer.address);
  console.log(`\n=== Staking Flow Test on Coston2 ===`);
  console.log(`Deployer: ${deployer.address}`);
  console.log(`Balance:  ${ethers.formatEther(balance)} C2FLR\n`);

  const registry = await ethers.getContractAt("AgentRegistry", ADDRESSES.AgentRegistry);
  const staking = await ethers.getContractAt("AgentStaking", ADDRESSES.AgentStaking);

  // Use a deterministic test agent address
  const testAgentWallet = ethers.Wallet.createRandom();
  const testAgent = testAgentWallet.address;
  console.log(`Test agent address: ${testAgent}\n`);

  // ─── Step 1: Register agent ───────────────────────────
  console.log("--- Step 1: Register agent in AgentRegistry ---");
  const regTx = await registry.registerAgent(
    testAgent,
    "TestStakingAgent",
    "ipfs://test-metadata",
    ["data_analysis"]
  );
  await regTx.wait();
  console.log("Agent registered");

  const agentInfo = await registry.getAgent(testAgent);
  console.log(`  Name: ${agentInfo.name}`);
  console.log(`  Developer: ${agentInfo.developer}`);
  console.log(`  Status: ${agentInfo.status} (1=Active)`);
  console.log(`  Active: ${await registry.isAgentActive(testAgent)}`);
  await delay(3000);

  // ─── Step 2: Stake ────────────────────────────────────
  console.log("\n--- Step 2: Stake 50 FLR ---");
  const stakeAmount = ethers.parseEther("50");
  const stakeTx = await staking.stake(testAgent, { value: stakeAmount });
  const stakeReceipt = await stakeTx.wait();
  console.log(`  Tx: ${stakeReceipt!.hash}`);

  let info = await staking.getStakeInfo(testAgent);
  console.log(`  isStaked: ${info.isStaked}`);
  console.log(`  stakedAmount: ${ethers.formatEther(info.stakedAmount)} FLR`);
  console.log(`  accumulatedEarnings: ${ethers.formatEther(info.accumulatedEarnings)} FLR`);
  await delay(3000);

  // ─── Step 3: Credit earnings ──────────────────────────
  console.log("\n--- Step 3: Credit 10 FLR earnings ---");
  // Temporarily set escrow to deployer so we can call creditEarnings
  const realEscrow = await staking.escrow();
  console.log(`  Current escrow: ${realEscrow}`);

  const setEscrowTx1 = await staking.setEscrow(deployer.address);
  await setEscrowTx1.wait();
  console.log("  Escrow temporarily set to deployer");
  await delay(3000);

  const earningsAmount = ethers.parseEther("10");
  const creditTx = await staking.creditEarnings(testAgent, earningsAmount, {
    value: earningsAmount,
  });
  await creditTx.wait();
  console.log("  Earnings credited: 10 FLR");

  // Restore real escrow
  const setEscrowTx2 = await staking.setEscrow(realEscrow);
  await setEscrowTx2.wait();
  console.log(`  Escrow restored to: ${realEscrow}`);
  await delay(3000);

  info = await staking.getStakeInfo(testAgent);
  console.log(`  accumulatedEarnings: ${ethers.formatEther(info.accumulatedEarnings)} FLR`);

  // ─── Step 4: Preview cashout ──────────────────────────
  console.log("\n--- Step 4: Preview cashout ---");
  const preview = await staking.previewCashout(testAgent);
  console.log(`  Earnings:   ${ethers.formatEther(preview.earnings)} FLR`);
  console.log(`  House fee:  ${ethers.formatEther(preview.houseFee)} FLR`);
  console.log(`  Max payout: ${ethers.formatEther(preview.maxPayout)} FLR`);

  const poolBefore = await staking.getPoolSize();
  console.log(`  Pool size:  ${ethers.formatEther(poolBefore)} FLR`);

  // ─── Step 5: Cashout (gamble!) ────────────────────────
  console.log("\n--- Step 5: CASHOUT (50/50 gamble) ---");
  const balBefore = await deployer.provider!.getBalance(deployer.address);

  try {
    const cashoutTx = await staking.cashout(testAgent);
    const cashoutReceipt = await cashoutTx.wait();
    console.log(`  Tx: ${cashoutReceipt!.hash}`);

    // Parse events to determine outcome
    for (const log of cashoutReceipt!.logs) {
      try {
        const parsed = staking.interface.parseLog({
          topics: log.topics as string[],
          data: log.data,
        });
        if (parsed) {
          console.log(`  Event: ${parsed.name}`);
          if (parsed.name === "CashoutWin") {
            console.log(`  >> WIN! Payout: ${ethers.formatEther(parsed.args.payout)} FLR`);
          } else if (parsed.name === "CashoutLoss") {
            console.log(`  >> LOSE. Lost: ${ethers.formatEther(parsed.args.lostEarnings)} FLR to pool`);
          } else if (parsed.name === "HouseFeePaid") {
            console.log(`  House fee paid: ${ethers.formatEther(parsed.args.amount)} FLR`);
          }
        }
      } catch {}
    }
  } catch (err: any) {
    console.log(`  Cashout failed: ${err.reason || err.message}`);
    console.log("  (This can happen if RandomNumberV2 returns stale/insecure number)");
  }

  await delay(3000);

  // ─── Step 6: Post-cashout state ───────────────────────
  console.log("\n--- Step 6: Post-cashout state ---");
  info = await staking.getStakeInfo(testAgent);
  console.log(`  isStaked: ${info.isStaked}`);
  console.log(`  stakedAmount: ${ethers.formatEther(info.stakedAmount)} FLR`);
  console.log(`  accumulatedEarnings: ${ethers.formatEther(info.accumulatedEarnings)} FLR`);
  console.log(`  wins: ${info.wins.toString()}`);
  console.log(`  losses: ${info.losses.toString()}`);

  const poolAfter = await staking.getPoolSize();
  console.log(`  Pool size: ${ethers.formatEther(poolAfter)} FLR`);

  const balAfter = await deployer.provider!.getBalance(deployer.address);
  const balDiff = balAfter - balBefore;
  console.log(`  Balance change: ${balDiff >= 0 ? "+" : ""}${ethers.formatEther(balDiff)} FLR (includes gas)`);

  // ─── Step 7: Unstake ──────────────────────────────────
  console.log("\n--- Step 7: Unstake ---");
  // Must deactivate agent first
  console.log("  Deactivating agent...");
  const deactivateTx = await registry.updateAgent(
    testAgent,
    "TestStakingAgent",
    "ipfs://test-metadata",
    ["data_analysis"],
    2 // Status.Inactive
  );
  await deactivateTx.wait();
  console.log(`  Agent active: ${await registry.isAgentActive(testAgent)}`);
  await delay(3000);

  const unstakeTx = await staking.unstake(testAgent);
  const unstakeReceipt = await unstakeTx.wait();
  console.log(`  Unstake tx: ${unstakeReceipt!.hash}`);

  for (const log of unstakeReceipt!.logs) {
    try {
      const parsed = staking.interface.parseLog({
        topics: log.topics as string[],
        data: log.data,
      });
      if (parsed?.name === "Unstaked") {
        console.log(`  Stake returned: ${ethers.formatEther(parsed.args.amount)} FLR`);
        console.log(`  Forfeited earnings: ${ethers.formatEther(parsed.args.forfeitedEarnings)} FLR`);
      }
    } catch {}
  }

  info = await staking.getStakeInfo(testAgent);
  console.log(`  isStaked: ${info.isStaked}`);

  const finalBal = await deployer.provider!.getBalance(deployer.address);
  console.log(`\nFinal balance: ${ethers.formatEther(finalBal)} C2FLR`);
  console.log("\n=== Test complete ===\n");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

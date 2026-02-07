import { expect } from "chai";
import { ethers } from "hardhat";

describe("AgentStaking", function () {
  let deployer: any;
  let dev: any; // agent dev who stakes
  let poster: any;
  let other: any;

  let agentRegistry: any;
  let mockRandom: any;
  let staking: any;

  // Helpers for FlareEscrow integration tests
  let mockUpdater: any;
  let ftso: any;
  let fdcVerifier: any;
  let orderBook: any;
  let escrow: any;

  const MINIMUM_STAKE = ethers.parseEther("50");

  async function currentTimestamp(): Promise<number> {
    const block = await ethers.provider.getBlock("latest");
    return block!.timestamp;
  }

  beforeEach(async function () {
    [deployer, dev, poster, other] = await ethers.getSigners();

    // Deploy AgentRegistry
    agentRegistry = await ethers.deployContract("AgentRegistry", [
      deployer.address,
    ]);
    await agentRegistry.waitForDeployment();

    // Deploy MockRandomNumberV2
    mockRandom = await ethers.deployContract("MockRandomNumberV2");
    await mockRandom.waitForDeployment();

    // Set a fresh secure random with current timestamp
    const ts = await currentTimestamp();
    await mockRandom.setRandomNumber(42, true, ts);

    // Deploy AgentStaking
    staking = await ethers.deployContract("AgentStaking", [
      deployer.address,
      agentRegistry.target,
      mockRandom.target,
      MINIMUM_STAKE,
    ]);
    await staking.waitForDeployment();
  });

  // ─── Helper: register agent and make it active ────────────
  async function registerAgent(signer: any) {
    await agentRegistry
      .connect(signer)
      .registerAgent("TestAgent", "ipfs://meta", ["data_analysis"]);
  }

  // ─── Helper: deactivate agent ─────────────────────────────
  async function deactivateAgent(signer: any) {
    await agentRegistry
      .connect(signer)
      .updateAgent("TestAgent", "ipfs://meta", ["data_analysis"], 2); // 2 = Inactive
  }

  // ═══════════════════════════════════════════════════════════
  // Staking
  // ═══════════════════════════════════════════════════════════

  describe("stake()", function () {
    it("should allow an active agent to stake", async function () {
      await registerAgent(dev);

      await expect(
        staking.connect(dev).stake({ value: MINIMUM_STAKE })
      )
        .to.emit(staking, "Staked")
        .withArgs(dev.address, MINIMUM_STAKE);

      const info = await staking.getStakeInfo(dev.address);
      expect(info.isStaked).to.be.true;
      expect(info.stakedAmount).to.equal(MINIMUM_STAKE);
      expect(info.accumulatedEarnings).to.equal(0);
    });

    it("should reject stake below minimum", async function () {
      await registerAgent(dev);

      await expect(
        staking.connect(dev).stake({ value: ethers.parseEther("10") })
      ).to.be.revertedWith("AgentStaking: below minimum stake");
    });

    it("should reject stake if agent not active in registry", async function () {
      // dev has not registered
      await expect(
        staking.connect(dev).stake({ value: MINIMUM_STAKE })
      ).to.be.revertedWith("AgentStaking: agent not active in registry");
    });

    it("should reject double stake", async function () {
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });

      await expect(
        staking.connect(dev).stake({ value: MINIMUM_STAKE })
      ).to.be.revertedWith("AgentStaking: already staked");
    });

    it("should accept stake above minimum", async function () {
      await registerAgent(dev);
      const amount = ethers.parseEther("100");

      await staking.connect(dev).stake({ value: amount });

      const info = await staking.getStakeInfo(dev.address);
      expect(info.stakedAmount).to.equal(amount);
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Credit Earnings
  // ═══════════════════════════════════════════════════════════

  describe("creditEarnings()", function () {
    beforeEach(async function () {
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });

      // Set escrow to deployer for direct testing
      await staking.connect(deployer).setEscrow(deployer.address);
    });

    it("should credit earnings from escrow", async function () {
      const amount = ethers.parseEther("10");

      await expect(
        staking
          .connect(deployer)
          .creditEarnings(dev.address, amount, { value: amount })
      )
        .to.emit(staking, "EarningsCredited")
        .withArgs(dev.address, amount);

      const info = await staking.getStakeInfo(dev.address);
      expect(info.accumulatedEarnings).to.equal(amount);
    });

    it("should accumulate multiple earnings", async function () {
      const a1 = ethers.parseEther("5");
      const a2 = ethers.parseEther("15");

      await staking
        .connect(deployer)
        .creditEarnings(dev.address, a1, { value: a1 });
      await staking
        .connect(deployer)
        .creditEarnings(dev.address, a2, { value: a2 });

      const info = await staking.getStakeInfo(dev.address);
      expect(info.accumulatedEarnings).to.equal(a1 + a2);
    });

    it("should reject if caller is not escrow", async function () {
      const amount = ethers.parseEther("10");
      await expect(
        staking
          .connect(other)
          .creditEarnings(dev.address, amount, { value: amount })
      ).to.be.revertedWith("AgentStaking: caller is not escrow");
    });

    it("should reject value mismatch", async function () {
      await expect(
        staking
          .connect(deployer)
          .creditEarnings(dev.address, ethers.parseEther("10"), {
            value: ethers.parseEther("5"),
          })
      ).to.be.revertedWith("AgentStaking: value mismatch");
    });

    it("should reject if agent not staked", async function () {
      const amount = ethers.parseEther("10");
      await expect(
        staking
          .connect(deployer)
          .creditEarnings(other.address, amount, { value: amount })
      ).to.be.revertedWith("AgentStaking: agent not staked");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Cashout (gamble)
  // ═══════════════════════════════════════════════════════════

  describe("cashout()", function () {
    const earnings = ethers.parseEther("10");

    beforeEach(async function () {
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });
      await staking.connect(deployer).setEscrow(deployer.address);

      // Credit some earnings
      await staking
        .connect(deployer)
        .creditEarnings(dev.address, earnings, { value: earnings });
    });

    it("should pay 1x earnings on win when pool is empty", async function () {
      // Even number = win
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts); // 42 is even → win

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).cashout();
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      // Pool is empty, so bonus = 0, payout = earnings only
      expect(balAfter - balBefore + gasCost).to.equal(earnings);

      const info = await staking.getStakeInfo(dev.address);
      expect(info.accumulatedEarnings).to.equal(0);
      expect(info.wins).to.equal(1);
      expect(info.losses).to.equal(0);
    });

    it("should pay 2x earnings on win when pool has enough", async function () {
      // First, seed the pool by having a loss
      // Credit earnings to 'other', make them lose
      await registerAgent(other);
      await staking.connect(other).stake({ value: MINIMUM_STAKE });
      const otherEarnings = ethers.parseEther("20");
      await staking
        .connect(deployer)
        .creditEarnings(other.address, otherEarnings, {
          value: otherEarnings,
        });

      // Odd number = lose
      let ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts);
      await staking.connect(other).cashout();

      // Pool should now have 20 FLR
      expect(await staking.getPoolSize()).to.equal(otherEarnings);

      // Now dev cashes out with win (even number)
      ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts);

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).cashout();
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      // 2x earnings = 20 FLR (10 own + 10 from pool)
      const expectedPayout = earnings * 2n;
      expect(balAfter - balBefore + gasCost).to.equal(expectedPayout);

      // Pool should have decreased by 10
      expect(await staking.getPoolSize()).to.equal(
        otherEarnings - earnings
      );

      const info = await staking.getStakeInfo(dev.address);
      expect(info.wins).to.equal(1);
    });

    it("should lose earnings to pool on loss", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts); // 43 is odd → lose

      const poolBefore = await staking.getPoolSize();

      await expect(staking.connect(dev).cashout())
        .to.emit(staking, "CashoutLoss")
        .withArgs(dev.address, earnings);

      const poolAfter = await staking.getPoolSize();
      expect(poolAfter - poolBefore).to.equal(earnings);

      const info = await staking.getStakeInfo(dev.address);
      expect(info.accumulatedEarnings).to.equal(0);
      expect(info.losses).to.equal(1);
      expect(info.wins).to.equal(0);
    });

    it("should cap win bonus to available pool", async function () {
      // Seed pool with only 3 FLR (less than the 10 FLR earnings)
      const smallPool = ethers.parseEther("3");
      // Send FLR directly to the staking contract to seed pool
      // We'll use another agent's loss to seed a small pool
      await registerAgent(other);
      await staking.connect(other).stake({ value: MINIMUM_STAKE });
      await staking
        .connect(deployer)
        .creditEarnings(other.address, smallPool, { value: smallPool });

      let ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts); // lose
      await staking.connect(other).cashout();

      // Pool = 3 FLR
      expect(await staking.getPoolSize()).to.equal(smallPool);

      // Dev wins → should get earnings + min(earnings, pool) = 10 + 3 = 13
      ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, true, ts); // win

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).cashout();
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      const expectedPayout = earnings + smallPool;
      expect(balAfter - balBefore + gasCost).to.equal(expectedPayout);

      // Pool should be empty
      expect(await staking.getPoolSize()).to.equal(0);
    });

    it("should reject cashout with no earnings", async function () {
      // Cash out first to drain earnings
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(43, true, ts);
      await staking.connect(dev).cashout();

      await expect(staking.connect(dev).cashout()).to.be.revertedWith(
        "AgentStaking: no earnings"
      );
    });

    it("should reject cashout if not staked", async function () {
      await expect(staking.connect(other).cashout()).to.be.revertedWith(
        "AgentStaking: not staked"
      );
    });

    it("should reject cashout with insecure random number", async function () {
      const ts = await currentTimestamp();
      await mockRandom.setRandomNumber(42, false, ts); // not secure

      await expect(staking.connect(dev).cashout()).to.be.revertedWith(
        "AgentStaking: random number not secure"
      );
    });

    it("should reject cashout with stale random number", async function () {
      const ts = await currentTimestamp();
      // Set timestamp to 200 seconds ago (beyond 120s max age)
      await mockRandom.setRandomNumber(42, true, ts - 200);

      await expect(staking.connect(dev).cashout()).to.be.revertedWith(
        "AgentStaking: random number too stale"
      );
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Unstake
  // ═══════════════════════════════════════════════════════════

  describe("unstake()", function () {
    beforeEach(async function () {
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });
    });

    it("should return stake after deactivation", async function () {
      await deactivateAgent(dev);

      const balBefore = await ethers.provider.getBalance(dev.address);
      const tx = await staking.connect(dev).unstake();
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * receipt.gasPrice;
      const balAfter = await ethers.provider.getBalance(dev.address);

      expect(balAfter - balBefore + gasCost).to.equal(MINIMUM_STAKE);

      const info = await staking.getStakeInfo(dev.address);
      expect(info.isStaked).to.be.false;
      expect(info.stakedAmount).to.equal(0);
    });

    it("should forfeit uncashed earnings to pool on unstake", async function () {
      await staking.connect(deployer).setEscrow(deployer.address);
      const earnings = ethers.parseEther("15");
      await staking
        .connect(deployer)
        .creditEarnings(dev.address, earnings, { value: earnings });

      await deactivateAgent(dev);

      const poolBefore = await staking.getPoolSize();

      await expect(staking.connect(dev).unstake())
        .to.emit(staking, "Unstaked")
        .withArgs(dev.address, MINIMUM_STAKE, earnings);

      const poolAfter = await staking.getPoolSize();
      expect(poolAfter - poolBefore).to.equal(earnings);
    });

    it("should reject unstake if agent is still active", async function () {
      await expect(staking.connect(dev).unstake()).to.be.revertedWith(
        "AgentStaking: agent still active"
      );
    });

    it("should reject unstake if not staked", async function () {
      await expect(staking.connect(other).unstake()).to.be.revertedWith(
        "AgentStaking: not staked"
      );
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Views
  // ═══════════════════════════════════════════════════════════

  describe("Views", function () {
    it("isStaked returns false for non-staked agent", async function () {
      expect(await staking.isStaked(dev.address)).to.be.false;
    });

    it("isStaked returns true for staked agent", async function () {
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });
      expect(await staking.isStaked(dev.address)).to.be.true;
    });

    it("previewCashout returns correct values", async function () {
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });
      await staking.connect(deployer).setEscrow(deployer.address);

      const earnings = ethers.parseEther("10");
      await staking
        .connect(deployer)
        .creditEarnings(dev.address, earnings, { value: earnings });

      const [previewEarnings, maxPayout] = await staking.previewCashout(
        dev.address
      );
      // Pool is empty, so max payout = earnings (no bonus)
      expect(previewEarnings).to.equal(earnings);
      expect(maxPayout).to.equal(earnings);
    });

    it("getPoolSize returns accumulated loss pool", async function () {
      expect(await staking.getPoolSize()).to.equal(0);
    });
  });

  // ═══════════════════════════════════════════════════════════
  // Owner Config
  // ═══════════════════════════════════════════════════════════

  describe("Owner config", function () {
    it("should update minimum stake", async function () {
      const newMin = ethers.parseEther("100");
      await expect(staking.connect(deployer).setMinimumStake(newMin))
        .to.emit(staking, "MinimumStakeUpdated")
        .withArgs(newMin);
      expect(await staking.minimumStake()).to.equal(newMin);
    });

    it("should update escrow", async function () {
      await expect(staking.connect(deployer).setEscrow(other.address))
        .to.emit(staking, "EscrowUpdated")
        .withArgs(other.address);
      expect(await staking.escrow()).to.equal(other.address);
    });

    it("should reject non-owner config changes", async function () {
      await expect(
        staking.connect(dev).setMinimumStake(100)
      ).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");

      await expect(
        staking.connect(dev).setEscrow(dev.address)
      ).to.be.revertedWithCustomError(staking, "OwnableUnauthorizedAccount");
    });
  });

  // ═══════════════════════════════════════════════════════════
  // FlareEscrow Integration (earnings routing)
  // ═══════════════════════════════════════════════════════════

  describe("FlareEscrow integration", function () {
    beforeEach(async function () {
      // Full deployment like flare-orderbook.test.ts
      mockUpdater = await ethers.deployContract("MockFastUpdater");
      await mockUpdater.waitForDeployment();
      await mockUpdater.setPrice(0, 2500, 5); // FLR/USD = $0.025

      ftso = await ethers.deployContract("FTSOPriceConsumer", [
        deployer.address,
      ]);
      await ftso.waitForDeployment();
      await ftso.setFastUpdater(mockUpdater.target);

      fdcVerifier = await ethers.deployContract("FDCVerifier", [
        deployer.address,
      ]);
      await fdcVerifier.waitForDeployment();

      orderBook = await ethers.deployContract("FlareOrderBook", [
        deployer.address,
        ftso.target,
      ]);
      await orderBook.waitForDeployment();

      escrow = await ethers.deployContract("FlareEscrow", [
        deployer.address,
        ftso.target,
        deployer.address,
      ]);
      await escrow.waitForDeployment();

      // Wire
      await orderBook.setEscrow(escrow.target);
      await escrow.setOrderBook(orderBook.target);
      await escrow.setFdcVerifier(fdcVerifier.target);

      // Wire staking <-> escrow
      await staking.setEscrow(escrow.target);
      await escrow.setAgentStaking(staking.target);
    });

    it("should route FLR payout to staking for staked provider", async function () {
      // Register + stake dev as agent
      await registerAgent(dev);
      await staking.connect(dev).stake({ value: MINIMUM_STAKE });

      // Create and assign a job
      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);
      await orderBook.connect(poster).assignProvider(1, dev.address);

      // Fund escrow: 10 USD => 400 FLR
      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(1, dev.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      // Complete + FDC attest
      const proof = ethers.keccak256(ethers.toUtf8Bytes("done"));
      await orderBook.connect(dev).markCompleted(1, proof);
      await fdcVerifier.connect(deployer).manualConfirmDelivery(1);

      // Release — should route to staking, not directly to dev
      await escrow.connect(poster).releaseToProvider(1);

      // 400 FLR - 2% fee = 392 FLR credited as earnings
      const expectedEarnings = ethers.parseUnits("392", 18);
      const info = await staking.getStakeInfo(dev.address);
      expect(info.accumulatedEarnings).to.equal(expectedEarnings);
    });

    it("should pay directly to non-staked provider", async function () {
      // dev is NOT staked
      await registerAgent(dev);

      const deadline =
        (await ethers.provider.getBlock("latest"))!.timestamp + 86400;
      await orderBook
        .connect(poster)
        .createJob("ipfs://job", ethers.parseUnits("10", 18), deadline);
      await orderBook.connect(poster).assignProvider(1, dev.address);

      const flrNeeded = ethers.parseUnits("400", 18);
      await escrow
        .connect(poster)
        .fundJob(1, dev.address, ethers.parseUnits("10", 18), {
          value: flrNeeded,
        });

      const proof = ethers.keccak256(ethers.toUtf8Bytes("done"));
      await orderBook.connect(dev).markCompleted(1, proof);
      await fdcVerifier.connect(deployer).manualConfirmDelivery(1);

      // Should go directly to dev
      const balBefore = await ethers.provider.getBalance(dev.address);
      await escrow.connect(poster).releaseToProvider(1);
      const balAfter = await ethers.provider.getBalance(dev.address);

      const expectedPayout = ethers.parseUnits("392", 18);
      expect(balAfter - balBefore).to.equal(expectedPayout);
    });
  });
});

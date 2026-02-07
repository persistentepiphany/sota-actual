import { ethers } from "hardhat";

async function main() {
  const wallet = ethers.Wallet.createRandom();
  console.log("New wallet generated for Flare Coston2 deployments:\n");
  console.log(`Address: ${wallet.address}`);
  console.log(`Private Key: ${wallet.privateKey}`);
  console.log("Store the key securely before funding the wallet.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

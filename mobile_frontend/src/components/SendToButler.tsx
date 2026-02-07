"use client";

import React, { useState } from 'react';
import { useAccount, useSwitchChain, useWaitForTransactionReceipt, useWriteContract } from 'wagmi';
import { parseUnits } from 'viem';

const BUTLER_ADDRESS = process.env.NEXT_PUBLIC_BUTLER_ADDRESS || '0x741ae17d47d479e878adfb3c78b02db583c63d58';
const FLARE_COSTON2_ID = 114;
const STABLECOIN_ADDRESS = (process.env.NEXT_PUBLIC_STABLECOIN_ADDRESS ||
  '0x0000000000000000000000000000000000000000') as `0x${string}`;
const STABLECOIN_DECIMALS = 6;

const erc20Abi = [
  {
    name: 'transfer',
    type: 'function',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ type: 'bool' }],
  },
] as const;

export const SendToButler: React.FC = () => {
  const { isConnected, chainId } = useAccount();
  const { switchChainAsync, isPending: isSwitching } = useSwitchChain();
  const { data: hash, isPending: isSending, writeContractAsync, error } = useWriteContract();
  const { isLoading: isConfirming, isSuccess } = useWaitForTransactionReceipt({ hash });

  const [amount, setAmount] = useState('1.00');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSend = async () => {
    setLocalError(null);

    if (!isConnected) {
      setLocalError('Connect your wallet first.');
      return;
    }

    let value: bigint;
    try {
      value = parseUnits(amount.trim() || '0', STABLECOIN_DECIMALS);
      if (value <= BigInt(0)) {
        setLocalError('Enter an amount greater than 0.');
        return;
      }
    } catch (err) {
      setLocalError('Enter a valid amount.');
      return;
    }

    try {
      if (chainId !== FLARE_COSTON2_ID && switchChainAsync) {
        await switchChainAsync({ chainId: FLARE_COSTON2_ID });
      }

      await writeContractAsync({
        address: STABLECOIN_ADDRESS,
        abi: erc20Abi,
        functionName: 'transfer',
        args: [BUTLER_ADDRESS as `0x${string}`, value],
        chainId: FLARE_COSTON2_ID,
      });
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : String(err));
    }
  };

  const status = localError || error?.message;

  return (
    <div className="send-card">
      <div className="send-heading">
        <span className="send-title">Send Stablecoin to Butler</span>
        <span className="send-subtitle">Flare Coston2 · Plasma USDC</span>
      </div>

      <div className="send-target" title="Butler address">
        {BUTLER_ADDRESS}
      </div>

      <div className="send-input-row">
        <input
          type="text"
          inputMode="decimal"
          className="send-input"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.01"
        />
        <button
          type="button"
          className="btn-primary send-button"
          onClick={handleSend}
          disabled={isSending || isSwitching}
        >
          {isSending ? 'Sending…' : isSwitching ? 'Switching…' : 'Send'}
        </button>
      </div>

      <div className="send-status">
        {!isConnected && !status && 'Connect wallet to send.'}
        {status && <span className="send-status-error">{status}</span>}
        {isConfirming && 'Waiting for confirmation…'}
        {isSuccess && hash && (
          <a
            href={`https://coston2-explorer.flare.network/tx/${hash}`}
            target="_blank"
            rel="noreferrer"
            className="send-link"
          >
            View on Flare Explorer
          </a>
        )}
      </div>
    </div>
  );
};

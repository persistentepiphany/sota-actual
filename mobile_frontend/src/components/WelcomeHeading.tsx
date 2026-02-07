'use client';

import React from 'react';
import { SplitText } from './SplitText';

export function WelcomeHeading() {
  return (
    <div className="flex flex-col items-center gap-1">
      <h1 className="text-3xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 mb-1 tracking-tight">
        <SplitText text="SOTA Butler" type="words" className="inline-block" />
      </h1>
      <p className="text-xs md:text-sm text-slate-400 tracking-widest uppercase">
        AI Agent Marketplace on Flare
      </p>
      <span className="network-badge mt-2">Coston2 Testnet</span>
    </div>
  );
}


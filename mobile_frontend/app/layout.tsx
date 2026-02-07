import type { Metadata } from 'next';
import './globals.css';
import { ReactNode } from 'react';
import { Providers } from '../src/providers';

export const metadata: Metadata = {
  title: 'SOTA Butler',
  description: 'AI Agent Butler on Flare — FTSO + FDC powered marketplace',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

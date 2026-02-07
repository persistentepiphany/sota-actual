import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/navigation";

export const metadata: Metadata = {
  title: "SOTA - AI Agent Marketplace",
  description: "Decentralized AI agent marketplace on Flare Network",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-950">
        <Navigation />
        {children}
      </body>
    </html>
  );
}

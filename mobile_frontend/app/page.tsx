"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "motion/react";
import { MessageCircle, Wallet } from "lucide-react";
import { Providers } from "@/src/providers";
import ChatScreen from "@/src/components/ChatScreen";
import WalletScreen from "@/src/components/WalletScreen";

const Waves = dynamic(
  () => import("@/components/ui/wave-background").then((mod) => mod.Waves),
  { ssr: false }
);

type View = "chat" | "wallet";

export default function Home() {
  const [activeView, setActiveView] = useState<View>("chat");

  return (
    <Providers>
      {/* ── Full-page wave background ── */}
      <Waves
        className="fixed inset-0 w-full h-full"
        strokeColor="rgba(99, 102, 241, 0.12)"
        backgroundColor="#020617"
        pointerSize={0.4}
      />

      {/* ── App shell ── */}
      <div className="app-shell">
        {/* ── Top nav bar ── */}
        <motion.nav
          className="top-nav"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        >
          <div className="top-nav-pills">
            {([
              { id: "chat" as View, icon: MessageCircle, label: "Butler" },
              { id: "wallet" as View, icon: Wallet, label: "Wallet" },
            ]).map((item) => {
              const isActive = activeView === item.id;
              return (
                <motion.button
                  key={item.id}
                  className={`top-nav-item ${isActive ? "active" : ""}`}
                  onClick={() => setActiveView(item.id)}
                  whileTap={{ scale: 0.92 }}
                >
                  {isActive && (
                    <motion.div
                      className="top-nav-active-bg"
                      layoutId="navIndicator"
                      transition={{ type: "spring", stiffness: 400, damping: 28 }}
                    />
                  )}
                  <item.icon size={18} className="top-nav-icon" />
                  <span className="top-nav-label">{item.label}</span>
                </motion.button>
              );
            })}
          </div>
        </motion.nav>

        {/* ── Page content ── */}
        <AnimatePresence mode="wait">
          {activeView === "chat" && (
            <motion.div
              key="chat"
              className="app-view"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
            >
              <ChatScreen />
            </motion.div>
          )}
          {activeView === "wallet" && (
            <motion.div
              key="wallet"
              className="app-view"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              transition={{ duration: 0.3, ease: "easeInOut" }}
            >
              <WalletScreen />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Providers>
  );
}
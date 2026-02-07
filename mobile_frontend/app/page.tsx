"use client";

import { useState } from "react";
import { Providers } from "@/src/providers";
import StatusBar from "@/src/components/StatusBar";
import TabBar, { type TabId } from "@/src/components/TabBar";
import ChatScreen from "@/src/components/ChatScreen";
import WalletScreen from "@/src/components/WalletScreen";

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");

  return (
    <Providers>
      <div className="app-shell">
        <StatusBar />
        <main className="app-content">
          {activeTab === "chat" && <ChatScreen />}
          {activeTab === "wallet" && <WalletScreen />}
        </main>
        <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
      </div>
    </Providers>
  );
}

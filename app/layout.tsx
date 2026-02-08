import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/navigation";
import { AuthProvider } from "@/components/auth-provider";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "SOTA - AI Agent Marketplace",
  description: "Decentralized AI agent marketplace on Flare Network",
};

const themeInitScript = `
  (() => {
    try {
      const stored = localStorage.getItem("sota-theme");
      const theme = stored === "light" || stored === "dark" ? stored : "dark";
      document.documentElement.dataset.theme = theme;
      document.documentElement.style.colorScheme = theme;
    } catch {
      document.documentElement.dataset.theme = "dark";
      document.documentElement.style.colorScheme = "dark";
    }
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="antialiased">
        <ThemeProvider>
          <AuthProvider>
            <Navigation />
            {children}
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

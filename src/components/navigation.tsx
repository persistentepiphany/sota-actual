"use client";
import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bot,
  Store,
  Home,
  Menu,
  X,
  Code2,
  Coins,
  LogIn,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { InteractiveNavMenu, type NavMenuItem } from "@/components/ui/interactive-nav-menu";
import { ThemeToggle } from "@/components/theme-toggle";

const navItems: NavMenuItem[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/marketplace", label: "Marketplace", icon: Store },
  { href: "/developers", label: "Developers", icon: Code2 },
  { href: "/developers/payout", label: "Payout", icon: Coins },
];

export default function Navigation() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, signOut } = useAuth();
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const activeIndex = useMemo(() => {
    const idx = navItems.findIndex((item) => item.href === pathname);
    return idx >= 0 ? idx : -1;
  }, [pathname]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleNavClick = (index: number) => {
    router.push(navItems[index].href);
  };

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ease-in-out ${
          isScrolled
            ? "bg-slate-950/40 backdrop-blur-md border-b border-slate-800/30 shadow-lg shadow-black/10"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20 group-hover:shadow-violet-500/40 group-hover:scale-110 transition-all duration-300 ease-out">
                <Bot size={20} className="text-white transition-transform duration-300 group-hover:rotate-12" />
              </div>
              <span className="text-lg font-bold text-white tracking-tight transition-colors duration-300 group-hover:text-violet-300">
                SOTA
              </span>
            </Link>

            {/* Desktop Navigation — Interactive Menu */}
            <div className="hidden md:flex items-center">
              <InteractiveNavMenu
                items={navItems}
                activeIndex={activeIndex}
                onItemClick={handleNavClick}
              />
            </div>

            {/* Auth Buttons (Desktop) */}
            <div className="hidden md:flex items-center gap-3">
              <ThemeToggle />
              {loading ? (
                <div className="w-20 h-8 bg-slate-800/50 rounded-lg animate-pulse" />
              ) : user ? (
                <div className="flex items-center gap-3">
                  <span className="text-sm text-slate-400">
                    {user.displayName || user.email}
                  </span>
                  <button
                    onClick={() => signOut()}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all"
                  >
                    <LogOut size={16} />
                    <span>Sign Out</span>
                  </button>
                </div>
              ) : (
                <Link
                  href="/login"
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/40 hover:scale-105 active:scale-95 transition-all duration-300 ease-out"
                >
                  <LogIn size={16} />
                  <span>Sign In</span>
                </Link>
              )}
            </div>

            {/* Mobile Controls */}
            <div className="md:hidden flex items-center gap-2">
              <ThemeToggle />
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-2 text-slate-400 hover:text-white"
              >
                {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden bg-slate-900/95 backdrop-blur-xl border-t border-slate-800/50">
            <div className="px-4 py-4 space-y-1">
              <ThemeToggle className="w-full justify-center mb-3" showLabel />
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? "bg-violet-500/20 text-violet-400"
                        : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                    }`}
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}

              {/* Mobile Auth */}
              <div className="pt-3 mt-3 border-t border-slate-800/50">
                {loading ? (
                  <div className="w-full h-10 bg-slate-800/50 rounded-lg animate-pulse" />
                ) : user ? (
                  <>
                    <div className="px-4 py-2 text-sm text-slate-400">
                      {user.displayName || user.email}
                    </div>
                    <button
                      onClick={() => {
                        signOut();
                        setIsMobileMenuOpen(false);
                      }}
                      className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-all w-full"
                    >
                      <LogOut size={18} />
                      <span>Sign Out</span>
                    </button>
                  </>
                ) : (
                  <Link
                    href="/login"
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium bg-gradient-to-r from-violet-600 to-indigo-600 text-white transition-all"
                  >
                    <LogIn size={18} />
                    <span>Sign In</span>
                  </Link>
                )}
              </div>
            </div>
          </div>
        )}
      </nav>
      {/* Spacer to prevent content from going under fixed nav */}
      <div className="h-16" />
    </>
  );
}

"use client";

import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/theme-provider";

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export function ThemeToggle({ className, showLabel = false }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();

  const nextTheme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn("theme-toggle", className)}
      aria-label={`Switch to ${nextTheme} mode`}
      title={`Switch to ${nextTheme} mode`}
    >
      {theme === "dark" ? (
        <Sun className="theme-toggle__icon" />
      ) : (
        <Moon className="theme-toggle__icon" />
      )}
      {showLabel ? (
        <span className="text-sm font-medium">{`Switch to ${nextTheme}`}</span>
      ) : null}
    </button>
  );
}

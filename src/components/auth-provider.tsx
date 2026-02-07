"use client";

import React, { createContext, useContext, useState } from "react";

interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name?: string) => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading] = useState(false);

  const signIn = async (email: string, password: string) => {
    // TODO: Implement wallet-based auth for SOTA
    console.log("Sign in:", email);
    setUser({
      uid: "demo-user",
      email,
      displayName: email.split("@")[0],
    });
  };

  const signUp = async (email: string, password: string, name?: string) => {
    // TODO: Implement wallet-based auth for SOTA
    console.log("Sign up:", email, name);
    setUser({
      uid: "demo-user",
      email,
      displayName: name || email.split("@")[0],
    });
  };

  const signOut = async () => {
    setUser(null);
  };

  const getIdToken = async () => {
    return user ? "demo-token" : null;
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, signIn, signUp, signOut, getIdToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

"use client";
import { AccountShell } from "./account-shell";

// The Stage 1 entry point is the extracted mobile rehearsal app.
// Marketplace navigation replaces this shell in the next phase.
export function AppChrome({ children }: { children: React.ReactNode }) {
  return <AccountShell hideStatus>{children}</AccountShell>;
}

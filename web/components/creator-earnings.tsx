"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MobileAppFrame } from "./mobile-app-frame";

type Amount = { mint: string; amount_minor_units: number };
type Earnings = {
  totals: Amount[];
  paid_unlocks: number;
  characters: (Amount & { character_id: string; name: string })[];
  recent_transactions: (Amount & { signature: string; verified_at: string;
    characters: { name: string; amount_minor_units: number }[] })[];
};
const amount = (n: number) => (n / 1000000).toLocaleString("en-US", { maximumFractionDigits: 6 });
const short = (s: string) => s.slice(0, 6) + "…" + s.slice(-4);

export function CreatorEarnings() {
  const [data, setData] = useState<Earnings | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/payments/creator/earnings", { credentials: "same-origin", cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (response.status === 401) {
          window.dispatchEvent(new Event("echoloom-auth-required"));
          throw new Error("Sign in to view your creator earnings.");
        }
        if (!response.ok) throw new Error("Could not load earnings.");
        return response.json() as Promise<Earnings>;
      })
      .then(value => { if (!controller.signal.aborted) setData(value); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [reload]);

  return <MobileAppFrame className="rehearsal-app rh-earnings">
    <header className="rh-top">
      <Link className="rh-icon" href="/characters" aria-label="Back to characters">‹</Link>
      <div><span className="rh-top-title">Creator earnings</span><small>THE CHARACTER LIBRARY</small></div>
      <button className="rh-icon" aria-label="Refresh earnings" onClick={() => {
        setError(""); setData(null); setReload(n => n + 1);
      }}>↻</button>
    </header>
    <div className="rh-scroll rh-pad mc-library">
      <span className="rh-eyebrow">CREATOR STUDIO · DEVNET</span>
      <h1>Your earnings.</h1>
      <p className="rh-muted">Verified story unlocks only. Test tokens have no cash value.</p>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading earnings…</p>}
      {data && <>
        <section className="rh-unlock-plan">
          <small>Lifetime attributed earnings</small>
          {!data.totals.length && <strong>0 test tokens</strong>}
          {data.totals.map(t => <div key={t.mint}><strong>{amount(t.amount_minor_units)} test tokens</strong>
            <small title={t.mint}>Mint: {short(t.mint)}</small></div>)}
          <small>{data.paid_unlocks} verified paid story unlocks</small>
        </section>
        <h2>Earnings by character</h2>
        {!data.characters.length && <p className="rh-muted">No verified earnings yet.</p>}
        {data.characters.map(c => <div className="rh-unlock-plan" key={c.mint + c.character_id}>
          <strong>{c.name}</strong><small>{amount(c.amount_minor_units)} test tokens · {short(c.mint)}</small>
        </div>)}
        <h2>Recent transactions</h2>
        {!data.recent_transactions.length && <p className="rh-muted">Your verified purchases will appear here.</p>}
        {data.recent_transactions.map(t => <div className="rh-unlock-plan" key={t.signature}>
          <strong>+{amount(t.amount_minor_units)} test tokens</strong>
          <small>{t.characters.map(c => c.name).join(" · ")}</small>
          <small>{t.verified_at} · Mint: {short(t.mint)}</small>
          <a href={"https://explorer.solana.com/tx/" + encodeURIComponent(t.signature) + "?cluster=devnet"}
             target="_blank" rel="noreferrer">View transaction ↗</a>
        </div>)}
      </>}
      <p className="rh-muted">Only payments with recorded creator attribution are included. This is not a wallet balance.</p>
    </div>
  </MobileAppFrame>;
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MobileAppFrame } from "./mobile-app-frame";
import styles from "./creator-earnings.module.css";

type Amount = { mint: string; amount_minor_units: number };
type Earnings = {
  totals: Amount[];
  payout_wallet: string | null;
  listings: { character_id: string; listing_id: string; name: string; status: "enabled" | "setup_required" | "unpublished" }[];
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

  const multiMint = (data?.totals.length ?? 0) > 1;
  const [expanded, setExpanded] = useState(false);
  return <MobileAppFrame className="rehearsal-app rh-earnings">
    <header className="rh-top">
      <Link className="rh-icon" href="/characters" aria-label="Back to characters">‹</Link>
      <div><span className="rh-top-title">Creator earnings</span></div>
      <button className="rh-icon" aria-label="Refresh earnings" onClick={() => {
        setError(""); setData(null); setReload(n => n + 1);
      }}>↻</button>
    </header>
    <div className={"rh-scroll " + styles.content}>
      {error && <p role="alert" className={styles.muted}>{error}</p>}
      {!data && !error && <p role="status" className={styles.muted}>Loading earnings…</p>}
      {data && <>
        <section className={styles.summary} aria-label="Lifetime earnings">
          <div className={styles.summaryLabel}>Lifetime earnings <span>Devnet</span></div>
          {!data.totals.length && <div className={styles.total}>0 <small>tokens</small></div>}
          {data.totals.map(t => <div key={t.mint}>
            <div className={styles.total}>{amount(t.amount_minor_units)} <small>tokens</small></div>
            <p className={styles.mint} title={t.mint}>Mint: {short(t.mint)}</p>
          </div>)}
          <p className={styles.muted}>{data.paid_unlocks} paid story unlock{data.paid_unlocks === 1 ? "" : "s"}</p>
        </section>
        <div className={styles.walletRow}><div><strong>Payout wallet</strong><p className={styles.muted}>{data.payout_wallet ? short(data.payout_wallet) : "Not configured"}</p></div><Link href="/characters/publish">Manage →</Link></div>
        {data.listings.length === 0 && data.characters.length === 0 && data.recent_transactions.length === 0 ? (
          <section className={styles.empty}>
            <h2>No published characters yet</h2>
            <p className={styles.muted}>Publish a character to get started.</p>
            <Link href="/characters/publish">Publish a character →</Link>
          </section>
        ) : <>
          <section className={styles.section}>
            <h2>Your characters</h2>
            {data.listings.map(l => {
              const amounts = data.characters.filter(c => c.character_id === l.character_id);
              return <Link className={styles.row} key={l.listing_id} href={"/characters/publish?character=" + encodeURIComponent(l.character_id)}>
                <div className={styles.detail}><strong>{l.name}</strong><small className={l.status === "enabled" ? styles.enabled : undefined}>{l.status === "enabled" ? "Monetization enabled" : l.status === "unpublished" ? "Unpublished" : "Setup required"}</small></div>
                <div className={styles.values}>{amounts.length ? amounts.map(c => <span key={c.mint} title={c.mint}>{amount(c.amount_minor_units)}{multiMint ? " · " + short(c.mint) : ""}</span>) : <span>0.00</span>}<small>tokens</small></div>
              </Link>;
            })}
            {data.characters.filter(c => !data.listings.some(l => l.character_id === c.character_id)).map(c => <div className={styles.row} key={c.mint + c.character_id}>
              <div className={styles.detail}><strong>{c.name}</strong><small>Historical / private</small></div>
              <span className={styles.value}>{amount(c.amount_minor_units)}{multiMint ? " · " + short(c.mint) : ""}</span>
            </div>)}
          </section>
          <section className={styles.section}>
            <h2>Transactions</h2>
            {!data.recent_transactions.length && <p className={styles.muted}>No paid transactions yet.</p>}
            {data.recent_transactions.slice(0, expanded ? 50 : 3).map(t => <a
              className={styles.row + " " + styles.transaction}
              key={t.signature} href={"https://explorer.solana.com/tx/" + encodeURIComponent(t.signature) + "?cluster=devnet"}
              target="_blank" rel="noreferrer" aria-label={"View transaction " + t.signature}>
              <div className={styles.detail}><strong>{t.characters.map(c => c.name).join(" · ")}</strong>
                <small>{new Date(t.verified_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}{multiMint ? " · " + short(t.mint) : ""}</small></div>
              <span className={styles.value}>+{amount(t.amount_minor_units)} <span aria-hidden="true">↗</span></span>
            </a>)}
            {data.recent_transactions.length > 3 && <button className={styles.more} type="button"
              onClick={() => setExpanded(v => !v)}>{expanded ? "Show less" : "View all recent transactions"}</button>}
          </section>
        </>}
        <p className={styles.note}>Verified, attributed earnings only. Test tokens have no cash value; this is not a wallet balance.</p>
      </>}
    </div>
  </MobileAppFrame>;
}

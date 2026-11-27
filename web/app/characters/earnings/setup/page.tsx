"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { useSolanaWalletProvider, SOLANA_PAYMENT_CHAIN } from "@/components/solana-wallet-provider";

type Status = { wallet: string | null; approved: boolean; ready: boolean; setup_allowed: boolean };
async function request<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch("/api/payments/creator/" + path, {
    method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store",
    headers: body ? {"Content-Type":"application/json"} : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json();
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed.");
  return data;
}

export default function SetupEarnings() {
  const provider = useSolanaWalletProvider();
  const [status, setStatus] = useState<Status | null>(null);
  const [choice, setChoice] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [back, setBack] = useState("/characters/publish");
  const guard = useRef(false);
  const wallets = provider.wallets.filter(w => w.chains.includes(SOLANA_PAYMENT_CHAIN) && w.features["solana:signMessage"]);
  const selected = wallets.find(w => w.name === choice) ?? wallets[0];
  useEffect(() => {
    let active = true;
    const character = new URLSearchParams(window.location.search).get("character");
    if (character) setBack("/characters/publish?character=" + encodeURIComponent(character));
    request<Status>("setup").then(s => { if (active) setStatus(s); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  async function setup() {
    if (!selected || !consent || !status?.setup_allowed || guard.current) return;
    guard.current = true; setBusy(true); setError("");
    try {
      const account = await provider.connect(selected);
      if (!account.chains.includes(SOLANA_PAYMENT_CHAIN)) throw new Error("Select Solana Devnet in your wallet.");
      const challenge = await request<{challenge_id: string; message: string}>("wallet/challenge", {wallet: account.address});
      const signature = await provider.signMessage(selected, account, new TextEncoder().encode(challenge.message));
      if (signature.length !== 64) throw new Error("Invalid signature.");
      setStatus(await request<Status>("wallet/verify", {challenge_id:challenge.challenge_id,
        signature_b64:btoa(String.fromCharCode(...signature))}));
    } catch (e) { setError(e instanceof Error ? e.message : "Wallet setup failed."); }
    finally { guard.current = false; setBusy(false); }
  }

  return <main className="el-listing-editor" style={{maxWidth:540,margin:"0 auto",padding:"28px 20px 60px"}}>
    <Link href={back} style={{color:"#cdb8ff"}}>← Back to publishing</Link>
    <h1 style={{margin:"24px 0 12px"}}>Set up earnings</h1>
    <p style={{lineHeight:1.6,color:"#c6bad6"}}>Verify your account-level payout wallet once. You can use it for all eligible characters. No tokens are charged.</p>
    <section className="panel" style={{marginTop:24}}>
      {error && <p role="alert">{error}</p>}
      {!status && !error && <p role="status">Checking creator status…</p>}
      {status?.ready ? <>
        <h2>Payout wallet verified</h2><p style={{overflowWrap:"anywhere"}}>{status.wallet}</p>
        <p>Return to publishing, select Enable earnings and save your character.</p>
        <Link className="button primary full" href={back}>Continue to publishing →</Link>
      </> : status && !status.setup_allowed ? <p role="status">Creator approval required. Ask the demo operator to enable onboarding.</p>
      : status && <>
        <label htmlFor="payout-wallet">Payout wallet</label>
        <select id="payout-wallet" value={selected?.name ?? ""} onChange={e => setChoice(e.target.value)} disabled={busy || !wallets.length}>
          {!wallets.length && <option value="">No Devnet wallet detected</option>}
          {wallets.map(w => <option key={w.name} value={w.name}>{w.name}</option>)}
        </select>
        <label style={{display:"flex",gap:12,alignItems:"flex-start",margin:"20px 0"}}>
          <input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} disabled={busy} style={{width:18,height:18,flexShrink:0}}/>
          <span>I authorize this wallet to receive my creator payouts in Devnet test tokens. This does not authorize spending.</span>
        </label>
        <button type="button" className="button primary full" disabled={!selected || !consent || busy} onClick={()=>void setup()}>
          {busy ? "Check your wallet to approve the signature…" : "Connect and verify wallet"}
        </button>
      </>}
    </section>
    <p style={{marginTop:20,color:"#b9accd",fontSize:13}}>Use a separate buyer wallet when purchasing stories featuring your own paid character. Payout wallet rotation is not available yet.</p>
  </main>;
}

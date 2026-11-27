"use client";

import { useEffect, useRef, useState } from "react";
import { localGet, localPut } from "./rehearsal-api";
import { useSolanaWalletProvider, SOLANA_PAYMENT_CHAIN, type StandardWallet, type WalletAccount } from "./solana-wallet-provider";
import { purchaseSignedQuote } from "./rehearsal-solana-transaction";

/** Integration boundary: Ibrahim's wallet adapter supplies the implementation.
 * Never accept an adapter result as proof of payment; only verify API can unlock.
 * Register before mounting checkout; absent adapter keeps checkout disabled.
 */
export type CheckoutQuote = {
  order_id: string;
  expires_at: string;
  program_id: string;
  mint: string;
  decimals: number;
  amount_minor_units: number;
  payout_lines: { wallet: string; amount_minor_units: number }[];
  config_pda: string;
  receipt_pda: string;
  signer_pubkey: string;
  authorization_message_b64: string;
  authorization_signature_b64: string;
};

type Saved = { order_id: string; tx_signature: string | null };
type Phase = "idle" | "connecting" | "review" | "sending" | "pending" | "paid" | "failed";
type Step = "connect" | "challenge" | "sign" | "bind" | "quote" | "prepare" | "approve" | "verify";

// Only non-payment operations may be timed out and retried. A wallet send
// may broadcast after its promise stalls, so never race it with a timeout.
async function walletWait<T>(promise: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([promise, new Promise<T>((_, reject) => {
      timer = setTimeout(() => reject(new Error("Wallet response timed out. Dismiss any old wallet prompt and retry.")), 90000);
    })]);
  } finally { if (timer !== undefined) clearTimeout(timer); }
}
type Verify = { status: "pending" | "paid" | "rejected"; reason: string | null;
  scene_allowance: { used: number; limit: number } };

async function payment<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch("/api/payments/" + path, {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    signal: AbortSignal.timeout(45000),
  });
  if (r.status === 401) window.dispatchEvent(new Event("echoloom-auth-required"));
  const value = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof value.detail === "string" ? value.detail : "Payment request failed.");
  return value as T;
}

export function CheckoutPanel({sceneId, language, available, onPaid, onClose}: {
  sceneId: string; language: "en" | "zh"; available: boolean;
  onPaid: () => Promise<void>; onClose: () => void;
}) {
  const tr = (en: string, zh: string) => language === "zh" ? zh : en;
  const key = "checkout:" + sceneId;
  const [saved, setSaved] = useState<Saved | null>(() => localGet(key, null));
  const [phase, setPhase] = useState<Phase>(() => localGet<Saved | null>(key, null) ? "pending" : "idle");
  const [quote, setQuote] = useState<CheckoutQuote | null>(null);
  const [error, setError] = useState("");
  const [step, setStep] = useState<Step>("connect");
  const [polls, setPolls] = useState(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [signatureInput, setSignatureInput] = useState("");
  const guard = useRef(false);
  const provider = useSolanaWalletProvider();
  const [selectedWallet, setSelectedWallet] = useState("");
  const [connected, setConnected] = useState<{wallet: StandardWallet; account: WalletAccount} | null>(null);
  const wallets = provider.wallets.filter(w => w.chains.includes(SOLANA_PAYMENT_CHAIN)
    && w.features["solana:signMessage"] && w.features["solana:signAndSendTransaction"]);
  const selected = wallets.find(w => w.name === selectedWallet) ?? wallets[0];
  const working = phase === "connecting" || phase === "sending";
  const ready = available && !!connected;

  function persist(value: Saved | null) {
    if (!localPut(key, value)) throw new Error("Cannot save payment recovery data. Enable browser storage before continuing.");
    if (mounted.current) setSaved(value);
  }

  async function run(fn: () => Promise<void>) {
    if (guard.current) return;
    guard.current = true;
    setError("");
    try { await fn(); }
    catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed.");
      setPhase("failed");
    } finally { guard.current = false; }
  }

  async function check(order: Saved) {
    if (!order.tx_signature) return;
    setPhase("sending");
    setStep("verify");
    const result = await payment<Verify>("verify", order);
    if (!mounted.current) return;
    if (result.status === "paid") {
      setPhase("paid");
      // Retain recovery record until refresh succeeds.
      await onPaid();
      persist(null);
    } else {
      setPhase(result.status === "pending" ? "pending" : "failed");
      setError(result.reason || "");
    }
  }

  function connect() {
    if (!selected || saved) return;
    void run(async () => {
      setPhase("connecting");
      setStep("connect");
      const account = await walletWait(provider.connect(selected));
      if (!mounted.current) return;
      if (!account.chains.includes(SOLANA_PAYMENT_CHAIN)) throw new Error("Select Solana Devnet in your wallet.");
      setStep("challenge");
      const challenge = await payment<{challenge_id:string; message:string}>("wallet/challenge", {wallet:account.address});
      if (!mounted.current) return;
      setStep("sign");
      const signature = await walletWait(provider.signMessage(selected, account, new TextEncoder().encode(challenge.message)));
      if (!mounted.current) return;
      if (signature.length !== 64) throw new Error("Invalid wallet signature.");
      setStep("bind");
      await payment("wallet/verify", {challenge_id:challenge.challenge_id,
        signature_b64:btoa(String.fromCharCode(...signature))});
      if (!mounted.current) return;
      setConnected({wallet:selected,account});
      setPhase("idle");
    });
  }

  function requestQuote() {
    if (!connected || !ready || saved) return;
    void run(async () => {
      setPhase("connecting");
      setStep("quote");
      const q = await payment<CheckoutQuote>("quote", {scene_id:sceneId,buyer_wallet:connected.account.address});
      if (!mounted.current) return;
      setQuote(q);
      setPhase("review");
    });
  }

  function purchase() {
    if (!connected || !ready || !quote || saved) return;
    void run(async () => {
      if (Date.parse(quote.expires_at) <= Date.now()) {
        setQuote(null);
        setPhase("idle");
        throw new Error("Quote expired. Connect again for a fresh quote.");
      }
      setPhase("sending");
      setStep("prepare");
      // Save the order before requesting a wallet transaction. An ambiguous
      // broadcast must not silently trigger a second purchase.
      const order = {order_id:quote.order_id,tx_signature:null};
      persist(order);
      const signature = await purchaseSignedQuote(quote, connected.account.address, wire => {
        setStep("approve");
        return provider.signAndSendTransaction(connected.wallet, connected.account, SOLANA_PAYMENT_CHAIN, wire,
          {preflightCommitment:"confirmed"});
      });
      const submitted = {...order,tx_signature:signature};
      persist(submitted);
      if (mounted.current) await check(submitted);
    });
  }

  // Poll only verification of an existing signature. Never submit a second
  // transaction automatically. Bounded polling resumes when sheet reopens.
  useEffect(() => {
    if (phase !== "pending" || !saved?.tx_signature || polls >= 12) return;
    const timer = setTimeout(() => {
      if (guard.current) return;
      setPolls(n => n + 1);
      void run(() => check(saved));
    }, 5000);
    return () => clearTimeout(timer);
    // Functions close over the current order and callbacks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, saved, polls]);

  const stepText: Record<Step, string> = {
    connect: tr("Waiting for wallet connection…","等待钱包连接…"),
    challenge: tr("Requesting verification challenge…","正在获取验证请求…"),
    sign: tr("Open your wallet and approve the verification signature. No payment is requested.","请打开钱包并确认身份验证签名，不会扣款。"),
    bind: tr("Verifying wallet ownership…","正在验证钱包归属…"),
    quote: tr("Preparing payment quote…","正在获取付款报价…"),
    prepare: tr("Preparing transaction and token accounts…","正在准备交易与代币账户…"),
    approve: tr("Open your wallet to review and approve the transaction.","请打开钱包审核并确认交易。"),
    verify: tr("Checking transaction on Solana…","正在核验链上交易…"),
  };

  return (
    <div className="rh-unlock-sheet">
      <p className="rh-eyebrow">{tr("CONTINUE YOUR STORY","继续你的故事")}</p>
      <h2>{tr("Your story is just beginning.","故事，才刚刚开始。")}</h2>
      <div className="rh-unlock-plan">
        <strong>{tr("+40 story sentences","+40 句剧情")}</strong>
        <small>{tr("1 test token · Solana Devnet · No expiration on purchased sentences",
          "1 枚测试代币 · Solana Devnet · 已购买额度不过期")}</small>
        {quote && <small>{tr("Quoted amount: ","报价：")}{quote.amount_minor_units / 10 ** quote.decimals}
          {" · "}{tr("Expires: ","到期：")}{new Date(quote.expires_at).toLocaleTimeString()}</small>}
      </div>
      {!available && !saved && <p role="status">{tr("Wallet verification is available. Payments are not enabled for this scene or deployment.",
        "可以验证钱包；当前场景或部署尚未开启付款。")}</p>}
      {!connected && !saved && wallets.length === 0 && <p role="status">{tr("No Devnet-compatible wallet detected. Install or unlock Phantom or Solflare.","未检测到兼容 Devnet 的钱包，请安装或解锁 Phantom 或 Solflare。")}</p>}
      {!connected && !saved && wallets.length > 0 && <label>{tr("Wallet","钱包")}
        <select value={selected?.name ?? ""} onChange={e => setSelectedWallet(e.target.value)}>
          {wallets.map(w => <option key={w.name} value={w.name}>{w.name}</option>)}
        </select>
      </label>}
      {connected && <p role="status">{tr("Verified wallet: ","已验证钱包：")}{connected.account.address.slice(0,6)}…{connected.account.address.slice(-4)}</p>}
      {working && <p role="status" aria-live="polite">{stepText[step]}</p>}
      {phase === "pending" && <p role="status">{polls < 12 && saved?.tx_signature ? tr("Payment confirmation pending. Checking automatically…","等待付款确认，正在自动查询…") : tr("Payment confirmation pending. Check again when ready.","等待付款确认，请稍后手动查询。")}</p>}
      {phase === "paid" && <p role="status">{tr("Payment verified.","付款已核验。")}</p>}
      {error && <p role="alert">{error}</p>}
      {!saved && !connected && phase !== "paid" && phase !== "review" && <button className="rh-primary"
        disabled={!selected || working} onClick={connect}>{tr("Connect wallet","连接钱包")}</button>}
      {!saved && connected && phase !== "review" && phase !== "paid" && <button className="rh-primary"
        disabled={!ready || working} onClick={requestQuote}>{tr("Get payment quote","获取付款报价")}</button>}
      {!saved && phase === "review" && <button className="rh-primary"
        disabled={!ready || working} onClick={purchase}>{tr("Confirm payment","确认付款")}</button>}
      {saved && !saved.tx_signature && !working && <>
        <p>{tr("If the wallet submitted a transaction, paste its signature to recover this order. Do not pay again.",
          "如果钱包已发送交易，请粘贴交易签名恢复订单。不要重复付款。")}</p>
        <label>{tr("Transaction signature","交易签名")}
          <input value={signatureInput} onChange={e => setSignatureInput(e.target.value)} />
        </label>
        <button className="rh-primary" disabled={!signatureInput.trim()} onClick={() => void run(async () => {
          const recovered = {...saved,tx_signature:signatureInput.trim()};
          persist(recovered);
          await check(recovered);
        })}>{tr("Recover payment","恢复付款")}</button>
      </>}
      {saved?.tx_signature && !working && <button className="rh-primary"
        onClick={() => { setPolls(0); void run(() => check(saved)); }}>{tr("Check payment again","重新核验付款")}</button>}
      <button className="rh-secondary" disabled={working} onClick={onClose}>{tr("Return to story","返回故事")}</button>
    </div>
  );
}

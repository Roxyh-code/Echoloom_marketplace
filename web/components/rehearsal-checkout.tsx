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
type WalletStatus = { wallet: string | null; verified: boolean };
async function walletStatus(signal?: AbortSignal): Promise<WalletStatus> {
  const r = await fetch("/api/payments/wallet", { credentials: "same-origin", cache: "no-store", signal });
  if (!r.ok) throw new Error("Could not check saved wallet.");
  return r.json();
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

export function CheckoutPanel({sceneId, language, available, onPaid, onClose, onBusy}: {
  sceneId: string; language: "en" | "zh"; available: boolean;
  onPaid: () => Promise<void>; onClose: () => void; onBusy?: (busy: boolean) => void;
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
  const [liveAvailable, setLiveAvailable] = useState<boolean | null>(null);
  const ready = (liveAvailable ?? available) && !!connected;
  const [boundWallet, setBoundWallet] = useState<string | null>(null);
  const attempted = useRef(new Set<StandardWallet>());
  const {wallets: registered, revision, restore} = provider;
  useEffect(() => {
    if (saved || guard.current || registered.length === 0) return;
    const controller = new AbortController();
    void (async () => {
      try {
        const status = await walletStatus(controller.signal);
        if (controller.signal.aborted || guard.current) return;
        setBoundWallet(status.verified ? status.wallet : null);
        if (!status.verified || !status.wallet) {
          setConnected(null);
          return;
        }
        const compatible = registered.filter(w => w.chains.includes(SOLANA_PAYMENT_CHAIN)
          && w.features["solana:signMessage"] && w.features["solana:signAndSendTransaction"]);
        for (const wallet of compatible) {
          let account = wallet.accounts[0];
          if (!account && !attempted.current.has(wallet)) {
            attempted.current.add(wallet);
            const restored = await restore(wallet).catch(() => null);
            if (controller.signal.aborted || guard.current) return;
            if (restored) account = restored;
          }
          if (account?.address === status.wallet && account.chains.includes(SOLANA_PAYMENT_CHAIN)) {
            setConnected({wallet, account});
            return;
          }
        }
        setConnected(null);
      } catch { if (!controller.signal.aborted && !guard.current) setConnected(null); }
    })();
    return () => controller.abort();
  }, [registered, revision, restore, saved]);

  // Wallet change events invalidate stale quotes and connections. Check again
  // immediately before payment; no transaction may use a stale account.
  useEffect(() => {
    if (!connected) return;
    const live = connected.wallet.accounts[0];
    if (!registered.includes(connected.wallet) || live?.address !== connected.account.address
      || !live.chains.includes(SOLANA_PAYMENT_CHAIN)) {
      setConnected(null);
      setQuote(null);
      if (!guard.current && !saved) setPhase("idle");
    }
  }, [registered, revision, connected, saved]);

  useEffect(() => {
    setLiveAvailable(null);
    if (!connected || saved) return;
    const controller = new AbortController();
    void fetch("/api/payments/readiness/" + encodeURIComponent(sceneId), {
      credentials: "same-origin", cache: "no-store", signal: controller.signal,
    }).then(async r => {
      if (!r.ok) throw new Error("Readiness unavailable");
      const result = await r.json();
      if (!controller.signal.aborted) setLiveAvailable(result.available === true);
    }).catch(() => { if (!controller.signal.aborted) setLiveAvailable(false); });
    return () => controller.abort();
  }, [sceneId, connected?.account.address, saved]);

  async function assertCurrent() {
    if (!connected || connected.wallet.accounts[0]?.address !== connected.account.address
      || !connected.wallet.accounts[0]?.chains.includes(SOLANA_PAYMENT_CHAIN)) {
      setConnected(null); setQuote(null);
      throw new Error("Wallet account changed. Reconnect before continuing.");
    }
    const status = await walletStatus();
    if (!status.verified || status.wallet !== connected.account.address || connected.wallet.accounts[0]?.address !== connected.account.address || !connected.wallet.accounts[0]?.chains.includes(SOLANA_PAYMENT_CHAIN)) {
      setConnected(null); setQuote(null);
      throw new Error("Wallet binding changed. Verify again.");
    }
  }

  function persist(value: Saved | null) {
    if (!localPut(key, value)) throw new Error("Cannot save payment recovery data. Enable browser storage before continuing.");
    if (mounted.current) setSaved(value);
  }

  async function run(fn: () => Promise<void>) {
    if (guard.current) return;
    guard.current = true;
    onBusy?.(true);
    setError("");
    try { await fn(); }
    catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed.");
      setPhase("failed");
    } finally { guard.current = false; onBusy?.(false); }
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
      const previous = await walletStatus();
      if (!mounted.current) return;
      if (previous.verified && previous.wallet === account.address) {
        setBoundWallet(account.address);
        setConnected({wallet:selected,account});
        setPhase("idle");
        return;
      }
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
      setBoundWallet(account.address);
      setConnected({wallet:selected,account});
      setPhase("idle");
    });
  }

  function requestQuote() {
    if (!connected || !ready || saved) return;
    void run(async () => {
      setPhase("connecting");
      setStep("quote");
      await assertCurrent();
      const q = await payment<CheckoutQuote>("quote", {scene_id:sceneId,buyer_wallet:connected.account.address});
      if (!mounted.current) return;
      setQuote(q);
      setPhase("review");
    });
  }

  function purchase() {
    if (!connected || !ready || !quote || saved) return;
    void run(async () => {
      await assertCurrent();
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
      const signature = await purchaseSignedQuote(quote, connected.account.address, async (wire, kind) => {
        if (!mounted.current) throw new Error("Checkout closed before transaction submission.");
        await assertCurrent();
        if (!mounted.current) throw new Error("Checkout closed before transaction submission.");
        // Setup transactions can create token accounts but cannot purchase.
        // Only persist ambiguous recovery immediately before the actual send.
        if (kind === "purchase") persist(order);
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
      {!(liveAvailable ?? available) && !saved && <p role="status">{tr("Wallet verification is available. Payments are not enabled for this scene or deployment.",
        "可以验证钱包；当前场景或部署尚未开启付款。")}</p>}
      {!connected && !saved && boundWallet && <p role="status">{tr("Saved verified wallet: ","已保存验证钱包：")}{boundWallet.slice(0,6)}…{boundWallet.slice(-4)}. {tr("Reconnect if locked or disconnected.","如钱包已锁定或断开，请重新连接。")}</p>}
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
      {!saved && connected && !working && phase !== "paid" && <button className="rh-secondary" onClick={() => { setConnected(null); setQuote(null); setPhase("idle"); }}>{tr("Change wallet","更换钱包")}</button>}
      {!saved && connected && phase === "review" && <button className="rh-primary"
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
      {saved?.tx_signature && !working && <>
        <button className="rh-primary" onClick={() => { setPolls(0); void run(() => check(saved)); }}>{tr("Check payment again","重新核验付款")}</button>
        {phase === "failed" && <details>
          <summary>{tr("Correct transaction signature","更正交易签名")}</summary>
          <label>{tr("Transaction signature","交易签名")}
            <input value={signatureInput} onChange={e => setSignatureInput(e.target.value)} />
          </label>
          <button className="rh-secondary" disabled={!signatureInput.trim()} onClick={() => void run(async () => {
            const recovered = {...saved,tx_signature:signatureInput.trim()};
            persist(recovered); setPolls(0); await check(recovered);
          })}>{tr("Verify corrected signature","核验更正后的签名")}</button>
        </details>}
      </>}
      <button className="rh-secondary" disabled={working} onClick={onClose}>{tr("Return to story","返回故事")}</button>
    </div>
  );
}

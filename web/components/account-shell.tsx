"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { api } from "./api";
import styles from "./account-shell.module.css";

export type AccountState = {
  authenticated: boolean;
  setup_required: boolean;
  username: string | null;
};

/** The same narrow, white Bazar canvas and wordmark used by Marketplace. */
function AccountPageFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className={styles.canvas}>
      <header className={styles.topbar}>
        <Link href="/marketplace" className={styles.brand} aria-label="Echoloom marketplace home">
          <img src="/echoloom-gothic-mark.svg" alt="" aria-hidden="true" className="el-brand-icon" />
          <span>Echoloom<span className={styles.brandDot}>.</span></span>
        </Link>
        <Link href="/marketplace" className={styles.exploreLink}>
          Explore <span aria-hidden="true">→</span>
        </Link>
      </header>
      <div className={styles.content}>{children}</div>
      <footer className={styles.footer}>
        <span>ECHOLOOM · CHARACTER STORIES</span>
        <span>LOCAL PREVIEW</span>
      </footer>
    </main>
  );
}

export function AccountForm({
  setup,
  onDone,
  compact = false,
}: {
  compact?: boolean;
  setup: boolean;
  onDone: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const id = useId();

  return (
    <section aria-labelledby={`${id}-title`} className={styles.authSection}>
      <div className={styles.intro}>
        <span className={styles.eyebrow}>YOUR STORY STUDIO</span>
        <h1 id={`${id}-title`} className={styles.heading}>
          {setup ? "Make it yours." : "Welcome back."}
        </h1>
        {!compact && (
          <p className={styles.description}>
            {setup
              ? "Save your characters and stories."
              : "Pick up where you left off."}
          </p>
        )}
      </div>

      <form
        className={styles.form}
        onSubmit={async (event) => {
          event.preventDefault();
          if (busy) return;
          setBusy(true);
          setError("");
          try {
            await api(`/account/${setup ? "register" : "login"}`, {
              username,
              password,
            });
            window.dispatchEvent(new Event("echoloom-account-change"));
            // The caller reloads the same URL, including ?character=... .
            onDone();
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : "Please try again.");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className={styles.formHeading}>
          <h2>{setup ? "Create account" : "Sign in"}</h2>
          <span>{setup ? "01 / START HERE" : "YOUR ACCOUNT"}</span>
        </div>

        <label className={styles.field} htmlFor={`${id}-username`}>
          <span>Username</span>
          <input
            id={`${id}-username`}
            required
            minLength={3}
            maxLength={80}
            pattern="[a-zA-Z0-9_.-]+"
            title="3–80 characters: letters, numbers, underscore, period, or hyphen"
            autoComplete="username"
            spellCheck={false}
            placeholder="Your username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={busy}
          />
        </label>

        <div className={styles.field}>
          <label htmlFor={`${id}-password`} className={styles.fieldLabel}>Password</label>
          <span className={styles.passwordRow}>
            <input
              id={`${id}-password`}
              required
              type={showPassword ? "text" : "password"}
              minLength={10}
              maxLength={128}
              autoComplete={setup ? "new-password" : "current-password"}
              placeholder={setup ? "At least 10 characters" : "Enter your password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
            />
            <button
              className={styles.passwordToggle}
              type="button"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              disabled={busy}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </span>
        </div>

        {error && (
          <p role="alert" className={styles.error}>{error}</p>
        )}

        <button className={styles.primaryButton} type="submit" disabled={busy}>
          {busy ? "Please wait…" : setup ? "Create account" : "Sign in"}
          {!busy && <span aria-hidden="true">→</span>}
        </button>
      </form>

      <p className={styles.note}>
        Local demo account: no password recovery. Use a unique password and keep this installation private.
      </p>
    </section>
  );
}

/** Public Marketplace routes stay browsable without a local account. */
function isPrivateRoute(pathname: string | null): boolean {
  if (pathname === null) return true;
  // Private Character detail is under the Marketplace URL hierarchy for a
  // consistent Discover UX, but still requires owner authentication.
  if (pathname.startsWith("/marketplace/private/")) return true;
  return !(
    pathname === "/" ||
    pathname === "/marketplace" ||
    pathname.startsWith("/marketplace/")
  );
}

export function AccountShell({
  children,
  hideStatus = false,
}: {
  children: React.ReactNode;
  hideStatus?: boolean;
}) {
  const pathname = usePathname();
  const privateRoute = isPrivateRoute(pathname);
  // Local bootstrap supports creating/rehearsing characters before the first
  // account exists (as the API already does). Publishing is different: it
  // always requires an authenticated owner, even on a fresh installation.
  const publishingRoute =
    pathname === "/characters/publish" ||
    pathname?.startsWith("/characters/publish/") === true;
  const [account, setAccount] = useState<AccountState | null>(null);
  const [statusError, setStatusError] = useState(false);

  useEffect(() => {
    let active = true;
    const refresh = () => {
      void api<AccountState>("/account/session")
        .then((next) => {
          if (!active) return;
          setAccount(next);
          setStatusError(false);
        })
        .catch(() => {
          if (active) setStatusError(true);
        });
    };
    refresh();
    window.addEventListener("echoloom-account-change", refresh);
    window.addEventListener("echoloom-auth-required", refresh);
    return () => {
      active = false;
      window.removeEventListener("echoloom-account-change", refresh);
      window.removeEventListener("echoloom-auth-required", refresh);
    };
  }, []);

  if (privateRoute && !account) {
    return (
      <AccountPageFrame>
        <section className={styles.statusSection} role="status">
          <span className={styles.eyebrow}>YOUR STORY STUDIO</span>
          <h1 className={styles.heading}>
            {statusError ? "Connection unavailable." : "Opening your library…"}
          </h1>
          <p className={styles.description}>
            {statusError
              ? "We couldn't check your local account. Make sure FastAPI is running."
              : "Checking your Echoloom account."}
          </p>
          {statusError && (
            <button className={styles.primaryButton} type="button" onClick={() => window.location.reload()}>
              Retry <span aria-hidden="true">→</span>
            </button>
          )}
        </section>
      </AccountPageFrame>
    );
  }

  if (
    privateRoute &&
    account &&
    !account.authenticated &&
    (!account.setup_required || publishingRoute)
  ) {
    return (
      <AccountPageFrame>
        <AccountForm setup={account.setup_required} onDone={() => window.location.reload()} />
      </AccountPageFrame>
    );
  }

  return (
    <>
      {account?.authenticated && !hideStatus && (
        <div className="account-status">
          <span>Local account: {account.username}</span>
          <button
            type="button"
            onClick={async () => {
              await api("/account/logout", {});
              window.location.reload();
            }}
          >
            Sign out
          </button>
        </div>
      )}
      {children}
    </>
  );
}

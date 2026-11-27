"use client";

import { getWallets } from "@wallet-standard/app";
import { useCallback, useEffect, useState } from "react";

export const SOLANA_PAYMENT_CHAIN = "solana:devnet";

export type WalletAccount = {
  address: string;
  chains: readonly string[];
};

export type StandardWallet = {
  name: string;
  chains: readonly string[];
  accounts: readonly WalletAccount[];
  features: Record<string, unknown>;
};

type ConnectOutput = { accounts: readonly WalletAccount[] };

function feature<T>(wallet: StandardWallet, name: string): T | null {
  return (wallet.features[name] as T | undefined) ?? null;
}

export function useSolanaWalletProvider() {
  const [wallets, setWallets] = useState<readonly StandardWallet[]>([]);

  useEffect(() => {
    const registry = getWallets();
    const update = () =>
      setWallets(registry.get() as readonly StandardWallet[]);
    update();
    const offRegister = registry.on("register", update);
    const offUnregister = registry.on("unregister", update);
    return () => {
      offRegister();
      offUnregister();
    };
  }, []);

  const connect = useCallback(
    async (
      wallet: StandardWallet,
      chain = SOLANA_PAYMENT_CHAIN,
    ): Promise<WalletAccount> => {
      if (!wallet.chains.includes(chain))
        throw Object.assign(
          new Error("wallet is not on the configured cluster"),
          {
            checkoutError: "wrong_network" as const,
          },
        );
      const connectFeature = feature<{
        connect: () => Promise<ConnectOutput>;
      }>(wallet, "standard:connect");
      const account = (await connectFeature?.connect())?.accounts[0];
      if (!account) throw new Error("wallet did not return an account");
      return account;
    },
    [],
  );

  const signMessage = useCallback(
    async (
      wallet: StandardWallet,
      account: WalletAccount,
      message: Uint8Array,
    ): Promise<Uint8Array> => {
      const signingFeature = feature<{
        signMessage: (input: {
          account: WalletAccount;
          message: Uint8Array;
        }) => Promise<{ signature: Uint8Array }[]>;
      }>(wallet, "solana:signMessage");
      if (!signingFeature)
        throw new Error("wallet cannot sign verification messages");
      const signature = (
        await signingFeature.signMessage({ account, message })
      )[0]?.signature;
      if (!signature) throw new Error("wallet did not return a signature");
      return signature;
    },
    [],
  );

  const signAndSendTransaction = useCallback(
    async (
      wallet: StandardWallet,
      account: WalletAccount,
      chain: string,
      transaction: Uint8Array,
      options?: { preflightCommitment?: string },
    ): Promise<Uint8Array> => {
      const signingFeature = feature<{
        signAndSendTransaction: (input: {
          account: WalletAccount;
          chain: string;
          transaction: Uint8Array;
          options?: { preflightCommitment?: string };
        }) => Promise<{ signature: Uint8Array }[]>;
      }>(wallet, "solana:signAndSendTransaction");
      if (!signingFeature)
        throw new Error("wallet cannot sign and send Solana transactions");
      const signature = (
        await signingFeature.signAndSendTransaction({
          account,
          chain,
          transaction,
          options,
        })
      )[0]?.signature;
      if (!signature) throw new Error("wallet did not return a signature");
      return signature;
    },
    [],
  );

  return { wallets, connect, signMessage, signAndSendTransaction };
}

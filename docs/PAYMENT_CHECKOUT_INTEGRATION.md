# Checkout integration (PR 7)

The story checkout UI is ready for a wallet adapter, but checkout remains disabled until the integration branch supplies one and the server reports availability. Do not enable checkout in main until the Devnet smoke test succeeds.

Register an implementation of `CheckoutWallet` from `web/components/rehearsal-checkout.tsx` before checkout mounts. Ibrahim owns wallet discovery/connection and transaction construction. The adapter must retain the selected account, use Solana Devnet, sign the exact UTF-8 challenge bytes, construct the transaction from the signed quote and return the base58 signature. It must not invoke legacy quote/prepare endpoints.

Backend endpoints: POST /api/payments/wallet/challenge {wallet}; POST /api/payments/wallet/verify {challenge_id, signature_b64}; POST /api/payments/quote {scene_id,buyer_wallet}; POST /api/payments/verify {order_id,tx_signature}.

The UI saves the order before wallet submission, preserves ambiguous broadcasts and supports manual signature recovery. Only the verify API's paid result unlocks the story. No client-provided allowance is trusted. Follow-up: supply wallet adapter, enable server checkout availability only for eligible scenes, support safe cancellation/recovery of unsigned orders, and test actual Devnet flow.

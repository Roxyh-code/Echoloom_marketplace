use anchor_lang::prelude::*;

#[error_code]
pub enum MarketplaceError {
    #[msg("Unauthorized authority.")]
    Unauthorized,
    #[msg("Marketplace has already been initialized.")]
    AlreadyInitialized,
    #[msg("Invalid configuration.")]
    InvalidConfiguration,
    #[msg("The configured bootstrap authority did not sign.")]
    InvalidBootstrapAuthority,
    #[msg("Invalid or uninitialized payment mint.")]
    InvalidMint,
    #[msg("Only the classic SPL Token Program is supported.")]
    InvalidTokenProgram,
    #[msg("Invalid buyer.")]
    InvalidBuyer,
    #[msg("Invalid buyer token account.")]
    InvalidBuyerTokenAccount,
    #[msg("Invalid payout recipient.")]
    InvalidRecipient,
    #[msg("Invalid recipient token account.")]
    InvalidRecipientAccount,
    #[msg("Recipient count must be between one and three.")]
    InvalidRecipientCount,
    #[msg("Duplicate payout recipient.")]
    DuplicateRecipient,
    #[msg("Payout recipients must be sorted by raw public key bytes.")]
    UnsortedRecipients,
    #[msg("The buyer cannot receive a payout.")]
    BuyerCannotReceivePayout,
    #[msg("Invalid payout amounts.")]
    InvalidPayoutAmounts,
    #[msg("Payout total does not equal the authorized gross amount.")]
    InvalidTotalAmount,
    #[msg("Checked arithmetic overflow.")]
    ArithmeticOverflow,
    #[msg("Invalid purchase authorization.")]
    InvalidAuthorization,
    #[msg("Authorization signer does not match configuration.")]
    InvalidAuthorizationSigner,
    #[msg("Required Ed25519 instruction is missing or invalid.")]
    InvalidAuthorizationInstruction,
    #[msg("Ed25519 instruction contains invalid offsets.")]
    InvalidAuthorizationOffsets,
    #[msg("Purchase must be invoked at transaction level.")]
    InvalidInstructionStackHeight,
    #[msg("Authorization has expired.")]
    ExpiredAuthorization,
    #[msg("Authorization lifetime exceeds the configured maximum.")]
    AuthorizationLifetimeExceeded,
    #[msg("Invalid order reference hash.")]
    InvalidOrderReference,
    #[msg("This order has already been processed.")]
    PurchaseAlreadyProcessed,
    #[msg("Invalid program-derived address.")]
    InvalidPda,
    #[msg("Unsupported account version.")]
    InvalidAccountVersion,
    #[msg("Marketplace is paused.")]
    MarketplacePaused,
    #[msg("Invalid authority rotation.")]
    InvalidAuthorityRotation,
    #[msg("SPL Token transfer failed.")]
    TokenTransferFailed,
    #[msg("Unsupported token program.")]
    UnsupportedTokenProgram,
    #[msg("PDA initialization failed.")]
    PrefundedAccountInitializationFailed,
    #[msg("Payment mint must have exactly six decimals.")]
    InvalidMintDecimals,
    #[msg("Payouts must include a positive payment to the configured treasury.")]
    MissingTreasuryPayout,
}

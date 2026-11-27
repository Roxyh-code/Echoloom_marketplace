use anchor_lang::prelude::*;

#[event]
pub struct MarketplaceInitialized {
    pub config: Pubkey,
    pub initializer: Pubkey,
    pub config_authority: Pubkey,
    pub mint: Pubkey,
    pub authorization_signer: Pubkey,
    pub config_version: u32,
}

#[event]
pub struct MarketplaceConfigUpdated {
    pub config: Pubkey,
    pub field: u8,
    pub old_value: Pubkey,
    pub new_value: Pubkey,
    pub authority: Pubkey,
    pub config_version: u32,
}

#[event]
pub struct MarketplacePaused {
    pub authority: Pubkey,
    pub config_version: u32,
    pub timestamp: i64,
}

#[event]
pub struct MarketplaceResumed {
    pub authority: Pubkey,
    pub config_version: u32,
    pub timestamp: i64,
}

#[event]
pub struct PurchaseExecuted {
    pub receipt: Pubkey,
    pub order_reference_hash: [u8; 32],
    pub buyer: Pubkey,
    pub mint: Pubkey,
    pub gross_amount: u64,
    pub recipient_count: u8,
    pub config_version: u32,
}

use anchor_lang::prelude::*;

#[account]
pub struct MarketplaceConfig {
    pub account_version: u8,
    pub bump: u8,
    pub config_authority: Pubkey,
    pub pause_authority: Pubkey,
    pub authorization_signer: Pubkey,
    pub payment_mint: Pubkey,
    pub token_program: Pubkey,
    pub platform_treasury_owner: Pubkey,
    pub deployment_domain_hash: [u8; 32],
    pub config_version: u32,
    pub paused: bool,
}

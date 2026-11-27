use anchor_lang::prelude::*;

use super::PayoutEntry;

#[account]
pub struct PurchaseReceipt {
    pub receipt_version: u8,
    pub bump: u8,
    pub buyer: Pubkey,
    pub order_reference_hash: [u8; 32],
    pub product_hash: [u8; 32],
    pub mint: Pubkey,
    pub gross_amount: u64,
    pub recipient_count: u8,
    pub recipients: [PayoutEntry; 3],
    pub config_version: u32,
    pub created_at_unix: i64,
    pub created_at_slot: u64,
}

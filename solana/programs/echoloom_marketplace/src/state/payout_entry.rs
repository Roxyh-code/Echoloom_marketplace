use anchor_lang::prelude::*;

#[derive(Debug, AnchorSerialize, AnchorDeserialize, Clone, Copy, Default, PartialEq, Eq)]
pub struct PayoutEntry {
    pub owner: Pubkey,
    pub amount: u64,
}

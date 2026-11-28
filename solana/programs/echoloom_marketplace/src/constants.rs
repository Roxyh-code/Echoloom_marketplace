use anchor_lang::prelude::*;

pub const CONFIG_SEED: &[u8] = b"marketplace_config";
pub const RECEIPT_SEED: &[u8] = b"purchase_receipt";
pub const CONFIG_VERSION: u8 = 1;
pub const RECEIPT_VERSION: u8 = 1;
pub const CONFIG_DATA_LEN: usize = 231;
pub const CONFIG_SPACE: usize = 8 + CONFIG_DATA_LEN;
pub const RECEIPT_DATA_LEN: usize = 279;
pub const RECEIPT_SPACE: usize = 8 + RECEIPT_DATA_LEN;
pub const AUTHORIZATION_SCHEMA_VERSION: u8 = 1;
pub const AUTHORIZATION_MESSAGE_LEN: usize = 462;
// The Quote window is 15 minutes (900 s). The program checks `expires_at - now <= cap`
// at execution time, so the cap must exceed the Quote window plus backend/cluster clock skew.
pub const MAX_AUTHORIZATION_LIFETIME_SECONDS: i64 = 1800;
pub const MAX_RECIPIENTS: usize = 3;
pub const PAYMENT_MINT_DECIMALS: u8 = 6;
pub const CLASSIC_TOKEN_PROGRAM_ID: Pubkey = anchor_spl::token::ID;
pub const ASSOCIATED_TOKEN_PROGRAM_ID: Pubkey = anchor_spl::associated_token::ID;
pub const ED25519_PROGRAM_ID: Pubkey = pubkey!("Ed25519SigVerify111111111111111111111111111");

include!(concat!(env!("OUT_DIR"), "/bootstrap_authority.rs"));

pub fn bootstrap_authority() -> Pubkey {
    Pubkey::new_from_array(BOOTSTRAP_AUTHORITY_BYTES)
}

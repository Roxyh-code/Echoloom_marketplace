pub mod marketplace_config;
pub mod payout_entry;
pub mod purchase_receipt;

pub use marketplace_config::*;
pub use payout_entry::*;
pub use purchase_receipt::*;

#[cfg(test)]
mod tests {
    use super::*;
    use anchor_lang::{prelude::*, AccountSerialize};

    #[test]
    fn persistent_account_serialized_sizes_match_contract() {
        let config = MarketplaceConfig {
            account_version: 1,
            bump: 255,
            config_authority: Pubkey::new_from_array([1; 32]),
            pause_authority: Pubkey::new_from_array([2; 32]),
            authorization_signer: Pubkey::new_from_array([3; 32]),
            payment_mint: Pubkey::new_from_array([4; 32]),
            token_program: anchor_spl::token::ID,
            platform_treasury_owner: Pubkey::new_from_array([5; 32]),
            deployment_domain_hash: [6; 32],
            config_version: 1,
            paused: false,
        };
        let mut config_data = Vec::new();
        config.try_serialize(&mut config_data).unwrap();
        assert_eq!(config_data.len(), 239);

        let receipt = PurchaseReceipt {
            receipt_version: 1,
            bump: 255,
            buyer: Pubkey::new_from_array([7; 32]),
            order_reference_hash: [8; 32],
            product_hash: [9; 32],
            mint: Pubkey::new_from_array([10; 32]),
            gross_amount: 11,
            recipient_count: 1,
            recipients: [PayoutEntry::default(); 3],
            config_version: 1,
            created_at_unix: 12,
            created_at_slot: 13,
        };
        let mut receipt_data = Vec::new();
        receipt.try_serialize(&mut receipt_data).unwrap();
        assert_eq!(receipt_data.len(), 287);
        let mut payout_data = Vec::new();
        PayoutEntry::default().serialize(&mut payout_data).unwrap();
        assert_eq!(payout_data.len(), 40);
    }
}

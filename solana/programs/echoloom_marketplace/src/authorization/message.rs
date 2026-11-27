use anchor_lang::prelude::*;
use sha2::{Digest, Sha256};

use crate::{constants::AUTHORIZATION_MESSAGE_LEN, errors::MarketplaceError, state::PayoutEntry};

pub struct AuthorizationFields {
    pub deployment_domain_hash: [u8; 32],
    pub program_id: Pubkey,
    pub config: Pubkey,
    pub order_reference_hash: [u8; 32],
    pub buyer: Pubkey,
    pub product_hash: [u8; 32],
    pub mint: Pubkey,
    pub token_program: Pubkey,
    pub gross_amount: u64,
    pub recipient_count: u8,
    pub recipients: [PayoutEntry; 3],
    pub config_version: u32,
    pub expires_at_unix: i64,
    pub nonce: [u8; 32],
}

impl AuthorizationFields {
    pub fn parse(message: &[u8]) -> Result<Self> {
        require!(
            message.len() == AUTHORIZATION_MESSAGE_LEN,
            MarketplaceError::InvalidAuthorization
        );
        require!(
            message[0..32] == authorization_domain_hash(),
            MarketplaceError::InvalidAuthorization
        );
        require!(message[32] == 1, MarketplaceError::InvalidAuthorization);
        let mut offset = 33;
        let deployment_domain_hash = read_array::<32>(message, &mut offset)?;
        let program_id = read_pubkey(message, &mut offset)?;
        let config = read_pubkey(message, &mut offset)?;
        let order_reference_hash = read_array::<32>(message, &mut offset)?;
        let buyer = read_pubkey(message, &mut offset)?;
        let product_hash = read_array::<32>(message, &mut offset)?;
        let mint = read_pubkey(message, &mut offset)?;
        let token_program = read_pubkey(message, &mut offset)?;
        let gross_amount = u64::from_le_bytes(read_array::<8>(message, &mut offset)?);
        let recipient_count = read_array::<1>(message, &mut offset)?[0];
        let mut recipients = [PayoutEntry::default(); 3];
        for recipient in &mut recipients {
            recipient.owner = read_pubkey(message, &mut offset)?;
            recipient.amount = u64::from_le_bytes(read_array::<8>(message, &mut offset)?);
        }
        let config_version = u32::from_le_bytes(read_array::<4>(message, &mut offset)?);
        let expires_at_unix = i64::from_le_bytes(read_array::<8>(message, &mut offset)?);
        let nonce = read_array::<32>(message, &mut offset)?;
        require!(
            offset == AUTHORIZATION_MESSAGE_LEN,
            MarketplaceError::InvalidAuthorization
        );
        Ok(Self {
            deployment_domain_hash,
            program_id,
            config,
            order_reference_hash,
            buyer,
            product_hash,
            mint,
            token_program,
            gross_amount,
            recipient_count,
            recipients,
            config_version,
            expires_at_unix,
            nonce,
        })
    }
}

pub fn authorization_domain_hash() -> [u8; 32] {
    Sha256::digest(b"echoloom:purchase-authorization:v1").into()
}

pub fn order_reference_hash(uuid_bytes: &[u8; 16]) -> [u8; 32] {
    hash_parts(&[b"echoloom:order-ref:v1", uuid_bytes])
}

pub fn product_hash(product_id: &str) -> Result<[u8; 32]> {
    let bytes = product_id.as_bytes();
    require!(
        (1..=128).contains(&bytes.len()),
        MarketplaceError::InvalidAuthorization
    );
    let length =
        u16::try_from(bytes.len()).map_err(|_| error!(MarketplaceError::InvalidAuthorization))?;
    Ok(hash_parts(&[
        b"echoloom:product:v1",
        &length.to_le_bytes(),
        bytes,
    ]))
}

fn hash_parts(parts: &[&[u8]]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    for part in parts {
        hasher.update(part);
    }
    hasher.finalize().into()
}

pub fn serialize(fields: &AuthorizationFields) -> Result<[u8; AUTHORIZATION_MESSAGE_LEN]> {
    let mut out = [0u8; AUTHORIZATION_MESSAGE_LEN];
    let mut offset = 0usize;
    put(&mut out, &mut offset, &authorization_domain_hash())?;
    put(&mut out, &mut offset, &[1])?;
    put(&mut out, &mut offset, &fields.deployment_domain_hash)?;
    put(&mut out, &mut offset, fields.program_id.as_ref())?;
    put(&mut out, &mut offset, fields.config.as_ref())?;
    put(&mut out, &mut offset, &fields.order_reference_hash)?;
    put(&mut out, &mut offset, fields.buyer.as_ref())?;
    put(&mut out, &mut offset, &fields.product_hash)?;
    put(&mut out, &mut offset, fields.mint.as_ref())?;
    put(&mut out, &mut offset, fields.token_program.as_ref())?;
    put(&mut out, &mut offset, &fields.gross_amount.to_le_bytes())?;
    put(&mut out, &mut offset, &[fields.recipient_count])?;
    for recipient in fields.recipients {
        put(&mut out, &mut offset, recipient.owner.as_ref())?;
        put(&mut out, &mut offset, &recipient.amount.to_le_bytes())?;
    }
    put(&mut out, &mut offset, &fields.config_version.to_le_bytes())?;
    put(&mut out, &mut offset, &fields.expires_at_unix.to_le_bytes())?;
    put(&mut out, &mut offset, &fields.nonce)?;
    require!(
        offset == AUTHORIZATION_MESSAGE_LEN,
        MarketplaceError::InvalidAuthorization
    );
    Ok(out)
}

fn put<const N: usize>(out: &mut [u8; N], offset: &mut usize, bytes: &[u8]) -> Result<()> {
    let end = offset
        .checked_add(bytes.len())
        .ok_or(MarketplaceError::ArithmeticOverflow)?;
    let target = out
        .get_mut(*offset..end)
        .ok_or(MarketplaceError::InvalidAuthorization)?;
    target.copy_from_slice(bytes);
    *offset = end;
    Ok(())
}

fn read_array<const N: usize>(message: &[u8], offset: &mut usize) -> Result<[u8; N]> {
    let end = offset
        .checked_add(N)
        .ok_or(MarketplaceError::ArithmeticOverflow)?;
    let bytes = message
        .get(*offset..end)
        .ok_or(MarketplaceError::InvalidAuthorization)?;
    *offset = end;
    bytes
        .try_into()
        .map_err(|_| error!(MarketplaceError::InvalidAuthorization))
}

fn read_pubkey(message: &[u8], offset: &mut usize) -> Result<Pubkey> {
    Ok(Pubkey::new_from_array(read_array::<32>(message, offset)?))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_message_round_trips_at_exact_offsets() {
        let fields = AuthorizationFields {
            deployment_domain_hash: [7; 32],
            program_id: Pubkey::new_from_array([1; 32]),
            config: Pubkey::new_from_array([2; 32]),
            order_reference_hash: [3; 32],
            buyer: Pubkey::new_from_array([4; 32]),
            product_hash: [5; 32],
            mint: Pubkey::new_from_array([6; 32]),
            token_program: anchor_spl::token::ID,
            gross_amount: 0x0102_0304_0506_0708,
            recipient_count: 1,
            recipients: [
                PayoutEntry {
                    owner: Pubkey::new_from_array([8; 32]),
                    amount: 17,
                },
                PayoutEntry::default(),
                PayoutEntry::default(),
            ],
            config_version: 0x1122_3344,
            expires_at_unix: 0x0102_0304_0506_0708,
            nonce: [9; 32],
        };
        let encoded = serialize(&fields).unwrap();
        assert_eq!(encoded.len(), AUTHORIZATION_MESSAGE_LEN);
        assert_eq!(&encoded[289..297], &fields.gross_amount.to_le_bytes());
        assert_eq!(encoded[297], 1);
        assert_eq!(&encoded[418..422], &fields.config_version.to_le_bytes());
        assert_eq!(&encoded[422..430], &fields.expires_at_unix.to_le_bytes());
        let decoded = AuthorizationFields::parse(&encoded).unwrap();
        assert_eq!(
            decoded.deployment_domain_hash,
            fields.deployment_domain_hash
        );
        assert_eq!(decoded.program_id, fields.program_id);
        assert_eq!(decoded.config, fields.config);
        assert_eq!(decoded.gross_amount, fields.gross_amount);
        assert_eq!(decoded.recipients, fields.recipients);
        assert_eq!(decoded.config_version, fields.config_version);
        assert_eq!(decoded.nonce, fields.nonce);
    }

    #[test]
    fn rejects_trailing_and_wrong_domain_messages() {
        let fields = AuthorizationFields {
            deployment_domain_hash: [7; 32],
            program_id: Pubkey::new_from_array([1; 32]),
            config: Pubkey::new_from_array([2; 32]),
            order_reference_hash: [3; 32],
            buyer: Pubkey::new_from_array([4; 32]),
            product_hash: [5; 32],
            mint: Pubkey::new_from_array([6; 32]),
            token_program: anchor_spl::token::ID,
            gross_amount: 1,
            recipient_count: 1,
            recipients: [PayoutEntry::default(); 3],
            config_version: 1,
            expires_at_unix: 1,
            nonce: [9; 32],
        };
        let mut encoded = serialize(&fields).unwrap().to_vec();
        encoded.push(0);
        assert!(AuthorizationFields::parse(&encoded).is_err());
        let mut encoded = serialize(&fields).unwrap();
        encoded[0] ^= 1;
        assert!(AuthorizationFields::parse(&encoded).is_err());
    }
}

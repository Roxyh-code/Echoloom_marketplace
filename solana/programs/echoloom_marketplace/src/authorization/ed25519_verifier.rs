use anchor_lang::{prelude::*, solana_program::instruction::get_stack_height};
use solana_instructions_sysvar::{load_current_index_checked, load_instruction_at_checked};

use crate::{
    constants::{AUTHORIZATION_MESSAGE_LEN, ED25519_PROGRAM_ID},
    errors::MarketplaceError,
};

const ED25519_HEADER_LEN: usize = 16;
const ED25519_SIGNATURE_LEN: usize = 64;
const ED25519_PUBKEY_LEN: usize = 32;
const SELF_INSTRUCTION_INDEX: u16 = u16::MAX;

pub fn verify_previous_instruction(
    instructions_sysvar: &AccountInfo,
    expected_signer: &Pubkey,
) -> Result<[u8; AUTHORIZATION_MESSAGE_LEN]> {
    require_keys_eq!(
        *instructions_sysvar.key,
        solana_instructions_sysvar::ID,
        MarketplaceError::InvalidAuthorizationInstruction
    );
    require!(
        get_stack_height()
            == anchor_lang::solana_program::instruction::TRANSACTION_LEVEL_STACK_HEIGHT,
        MarketplaceError::InvalidInstructionStackHeight
    );
    let current = load_current_index_checked(instructions_sysvar)
        .map_err(|_| error!(MarketplaceError::InvalidAuthorizationInstruction))?;
    require!(
        current > 0,
        MarketplaceError::InvalidAuthorizationInstruction
    );
    let instruction = load_instruction_at_checked((current - 1) as usize, instructions_sysvar)
        .map_err(|_| error!(MarketplaceError::InvalidAuthorizationInstruction))?;
    require_keys_eq!(
        instruction.program_id,
        ED25519_PROGRAM_ID,
        MarketplaceError::InvalidAuthorizationInstruction
    );
    require!(
        instruction.accounts.is_empty(),
        MarketplaceError::InvalidAuthorizationInstruction
    );

    let data = instruction.data;
    let expected_len =
        ED25519_HEADER_LEN + ED25519_SIGNATURE_LEN + ED25519_PUBKEY_LEN + AUTHORIZATION_MESSAGE_LEN;
    require!(
        data.len() == expected_len,
        MarketplaceError::InvalidAuthorizationInstruction
    );
    require!(
        data[0] == 1 && data[1] == 0,
        MarketplaceError::InvalidAuthorizationInstruction
    );

    let signature_offset = read_u16(&data, 2)?;
    let signature_instruction = read_u16(&data, 4)?;
    let public_key_offset = read_u16(&data, 6)?;
    let public_key_instruction = read_u16(&data, 8)?;
    let message_offset = read_u16(&data, 10)?;
    let message_size = read_u16(&data, 12)?;
    let message_instruction = read_u16(&data, 14)?;
    require!(
        signature_offset == (ED25519_HEADER_LEN + ED25519_PUBKEY_LEN) as u16
            && signature_instruction == SELF_INSTRUCTION_INDEX
            && public_key_offset == ED25519_HEADER_LEN as u16
            && public_key_instruction == SELF_INSTRUCTION_INDEX
            && message_offset
                == (ED25519_HEADER_LEN + ED25519_PUBKEY_LEN + ED25519_SIGNATURE_LEN) as u16
            && message_size == AUTHORIZATION_MESSAGE_LEN as u16
            && message_instruction == SELF_INSTRUCTION_INDEX,
        MarketplaceError::InvalidAuthorizationOffsets
    );
    let public_key_end = usize::from(public_key_offset) + ED25519_PUBKEY_LEN;
    let message_end = usize::from(message_offset) + usize::from(message_size);
    require!(
        public_key_end <= data.len() && message_end == data.len(),
        MarketplaceError::InvalidAuthorizationOffsets
    );
    require!(
        data[usize::from(public_key_offset)..public_key_end] == expected_signer.to_bytes(),
        MarketplaceError::InvalidAuthorizationSigner
    );
    data[usize::from(message_offset)..message_end]
        .try_into()
        .map_err(|_| error!(MarketplaceError::InvalidAuthorizationOffsets))
}

fn read_u16(data: &[u8], offset: usize) -> Result<u16> {
    let bytes: [u8; 2] = data
        .get(offset..offset + 2)
        .ok_or(MarketplaceError::InvalidAuthorizationOffsets)?
        .try_into()
        .map_err(|_| error!(MarketplaceError::InvalidAuthorizationOffsets))?;
    Ok(u16::from_le_bytes(bytes))
}

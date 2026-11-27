use anchor_lang::{prelude::*, solana_program::system_instruction};

use crate::errors::MarketplaceError;

pub fn create_pda_account<'info>(
    payer: &AccountInfo<'info>,
    target: &AccountInfo<'info>,
    system_program: &AccountInfo<'info>,
    space: usize,
    seeds: &[&[u8]],
) -> Result<()> {
    require_keys_eq!(
        *system_program.key,
        System::id(),
        MarketplaceError::InvalidConfiguration
    );
    require!(
        target.owner == &System::id() && target.data_is_empty() && !target.executable,
        MarketplaceError::PrefundedAccountInitializationFailed
    );

    let minimum = Rent::get()?.minimum_balance(space);
    if target.lamports() < minimum {
        let transfer =
            system_instruction::transfer(payer.key, target.key, minimum - target.lamports());
        anchor_lang::solana_program::program::invoke(
            &transfer,
            &[payer.clone(), target.clone(), system_program.clone()],
        )?;
    }

    let allocate = system_instruction::allocate(target.key, space as u64);
    anchor_lang::solana_program::program::invoke_signed(
        &allocate,
        &[target.clone(), system_program.clone()],
        &[seeds],
    )?;
    let assign = system_instruction::assign(target.key, &crate::ID);
    anchor_lang::solana_program::program::invoke_signed(
        &assign,
        &[target.clone(), system_program.clone()],
        &[seeds],
    )?;
    Ok(())
}

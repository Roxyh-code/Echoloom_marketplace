use anchor_lang::solana_program::{
    account_info::AccountInfo,
    entrypoint::ProgramResult,
    instruction::{AccountMeta, Instruction},
    program::invoke,
    program_error::ProgramError,
    pubkey::Pubkey,
};

anchor_lang::solana_program::entrypoint!(process_instruction);

fn process_instruction(
    _wrapper_id: &Pubkey,
    accounts: &[AccountInfo<'_>],
    data: &[u8],
) -> ProgramResult {
    let (target, forwarded) = accounts
        .split_first()
        .ok_or(ProgramError::NotEnoughAccountKeys)?;
    let metas = forwarded
        .iter()
        .map(|account| {
            if account.is_writable {
                AccountMeta::new(*account.key, account.is_signer)
            } else {
                AccountMeta::new_readonly(*account.key, account.is_signer)
            }
        })
        .collect();
    let instruction = Instruction {
        program_id: *target.key,
        accounts: metas,
        data: data.to_vec(),
    };
    invoke(&instruction, accounts)
}

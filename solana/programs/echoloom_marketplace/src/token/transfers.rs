use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, TransferChecked};

pub fn transfer_checked<'info>(
    token_program: &Program<'info, Token>,
    source: &Account<'info, TokenAccount>,
    mint: &Account<'info, Mint>,
    destination: &AccountInfo<'info>,
    authority: &Signer<'info>,
    amount: u64,
) -> Result<()> {
    token::transfer_checked(
        CpiContext::new(
            token_program.key(),
            TransferChecked {
                from: source.to_account_info(),
                mint: mint.to_account_info(),
                to: destination.clone(),
                authority: authority.to_account_info(),
            },
        ),
        amount,
        mint.decimals,
    )
}

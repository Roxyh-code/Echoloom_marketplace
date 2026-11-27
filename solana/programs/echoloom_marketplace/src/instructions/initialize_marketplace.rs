use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token};

use crate::{
    constants::{bootstrap_authority, CONFIG_SEED, CONFIG_SPACE, CONFIG_VERSION},
    errors::MarketplaceError,
    events::MarketplaceInitialized,
    state::MarketplaceConfig,
};

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct InitializeMarketplaceArgs {
    pub platform_treasury_owner: Pubkey,
    pub authorization_signer: Pubkey,
    pub pause_authority: Pubkey,
    pub deployment_domain_hash: [u8; 32],
}

#[derive(Accounts)]
pub struct InitializeMarketplace<'info> {
    #[account(mut)]
    pub bootstrap_authority: Signer<'info>,
    /// CHECK: canonical singleton PDA; initialized with the prefund-tolerant helper.
    #[account(mut, seeds = [CONFIG_SEED], bump)]
    pub config: UncheckedAccount<'info>,
    pub payment_mint: Account<'info, Mint>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

pub fn handle(ctx: Context<InitializeMarketplace>, args: InitializeMarketplaceArgs) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.bootstrap_authority.key(),
        bootstrap_authority(),
        MarketplaceError::InvalidBootstrapAuthority
    );
    require_keys_eq!(
        *ctx.accounts.payment_mint.to_account_info().owner,
        ctx.accounts.token_program.key(),
        MarketplaceError::InvalidMint
    );
    require_keys_eq!(
        ctx.accounts.token_program.key(),
        anchor_spl::token::ID,
        MarketplaceError::InvalidTokenProgram
    );
    require!(
        args.platform_treasury_owner != Pubkey::default()
            && args.authorization_signer != Pubkey::default()
            && args.pause_authority != Pubkey::default()
            && args.authorization_signer != ctx.accounts.bootstrap_authority.key()
            && args.pause_authority != ctx.accounts.bootstrap_authority.key()
            && args.authorization_signer != args.pause_authority,
        MarketplaceError::InvalidConfiguration
    );
    require!(
        args.deployment_domain_hash != [0; 32],
        MarketplaceError::InvalidConfiguration
    );

    let bump = ctx.bumps.config;
    require!(
        ctx.accounts.config.owner == &System::id(),
        MarketplaceError::AlreadyInitialized
    );
    let bump_seed = [bump];
    crate::instructions::pda_init::create_pda_account(
        &ctx.accounts.bootstrap_authority.to_account_info(),
        &ctx.accounts.config.to_account_info(),
        &ctx.accounts.system_program.to_account_info(),
        CONFIG_SPACE,
        &[CONFIG_SEED, &bump_seed],
    )?;

    let config = MarketplaceConfig {
        account_version: CONFIG_VERSION,
        bump,
        config_authority: ctx.accounts.bootstrap_authority.key(),
        pause_authority: args.pause_authority,
        authorization_signer: args.authorization_signer,
        payment_mint: ctx.accounts.payment_mint.key(),
        token_program: anchor_spl::token::ID,
        platform_treasury_owner: args.platform_treasury_owner,
        deployment_domain_hash: args.deployment_domain_hash,
        config_version: 1,
        paused: false,
    };
    config
        .try_serialize(&mut &mut ctx.accounts.config.try_borrow_mut_data()?[..])
        .map_err(|_| error!(MarketplaceError::PrefundedAccountInitializationFailed))?;

    emit!(MarketplaceInitialized {
        config: ctx.accounts.config.key(),
        initializer: ctx.accounts.bootstrap_authority.key(),
        config_authority: ctx.accounts.bootstrap_authority.key(),
        mint: ctx.accounts.payment_mint.key(),
        authorization_signer: args.authorization_signer,
        config_version: 1,
    });
    Ok(())
}

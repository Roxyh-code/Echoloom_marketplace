use anchor_lang::prelude::*;

use crate::{
    constants::CONFIG_SEED,
    errors::MarketplaceError,
    events::{MarketplacePaused, MarketplaceResumed},
    state::MarketplaceConfig,
};

#[derive(Accounts)]
pub struct PauseMarketplace<'info> {
    pub pause_authority: Signer<'info>,
    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
    pub clock: Sysvar<'info, Clock>,
}

#[derive(Accounts)]
pub struct ResumeMarketplace<'info> {
    pub config_authority: Signer<'info>,
    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
    pub clock: Sysvar<'info, Clock>,
}

pub fn pause(ctx: Context<PauseMarketplace>) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.pause_authority.key(),
        ctx.accounts.config.pause_authority,
        MarketplaceError::Unauthorized
    );
    require!(
        !ctx.accounts.config.paused,
        MarketplaceError::InvalidConfiguration
    );
    let version = ctx
        .accounts
        .config
        .config_version
        .checked_add(1)
        .ok_or(MarketplaceError::ArithmeticOverflow)?;
    ctx.accounts.config.config_version = version;
    ctx.accounts.config.paused = true;
    emit!(MarketplacePaused {
        authority: ctx.accounts.pause_authority.key(),
        config_version: version,
        timestamp: ctx.accounts.clock.unix_timestamp
    });
    Ok(())
}

pub fn resume(ctx: Context<ResumeMarketplace>) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.config_authority.key(),
        ctx.accounts.config.config_authority,
        MarketplaceError::Unauthorized
    );
    require!(
        ctx.accounts.config.paused,
        MarketplaceError::InvalidConfiguration
    );
    let version = ctx
        .accounts
        .config
        .config_version
        .checked_add(1)
        .ok_or(MarketplaceError::ArithmeticOverflow)?;
    ctx.accounts.config.config_version = version;
    ctx.accounts.config.paused = false;
    emit!(MarketplaceResumed {
        authority: ctx.accounts.config_authority.key(),
        config_version: version,
        timestamp: ctx.accounts.clock.unix_timestamp
    });
    Ok(())
}

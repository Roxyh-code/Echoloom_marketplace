use anchor_lang::prelude::*;

use crate::{
    constants::CONFIG_SEED, errors::MarketplaceError, events::MarketplaceConfigUpdated,
    state::MarketplaceConfig,
};

#[derive(Accounts)]
pub struct UpdateMarketplaceConfig<'info> {
    pub config_authority: Signer<'info>,
    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
}

pub fn handle(ctx: Context<UpdateMarketplaceConfig>, new_treasury: Pubkey) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.config_authority.key(),
        ctx.accounts.config.config_authority,
        MarketplaceError::Unauthorized
    );
    require!(
        new_treasury != Pubkey::default(),
        MarketplaceError::InvalidConfiguration
    );
    let old = ctx.accounts.config.platform_treasury_owner;
    require!(old != new_treasury, MarketplaceError::InvalidConfiguration);
    let version = ctx
        .accounts
        .config
        .config_version
        .checked_add(1)
        .ok_or(MarketplaceError::ArithmeticOverflow)?;
    ctx.accounts.config.platform_treasury_owner = new_treasury;
    ctx.accounts.config.config_version = version;
    emit!(MarketplaceConfigUpdated {
        config: ctx.accounts.config.key(),
        field: 1,
        old_value: old,
        new_value: new_treasury,
        authority: ctx.accounts.config_authority.key(),
        config_version: version,
    });
    Ok(())
}

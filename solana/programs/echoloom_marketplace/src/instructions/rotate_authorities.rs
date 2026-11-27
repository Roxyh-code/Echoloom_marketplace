use anchor_lang::prelude::*;

use crate::{
    constants::CONFIG_SEED, errors::MarketplaceError, events::MarketplaceConfigUpdated,
    state::MarketplaceConfig,
};

#[derive(Accounts)]
pub struct RotateAuthorizedSigner<'info> {
    pub config_authority: Signer<'info>,
    pub new_signer: Signer<'info>,
    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
}

#[derive(Accounts)]
pub struct RotateConfigAuthority<'info> {
    pub current_authority: Signer<'info>,
    pub new_authority: Signer<'info>,
    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
}

#[derive(Accounts)]
pub struct RotatePauseAuthority<'info> {
    pub config_authority: Signer<'info>,
    pub new_authority: Signer<'info>,
    #[account(mut, seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
}

pub fn rotate_authorized_signer(
    ctx: Context<RotateAuthorizedSigner>,
    requested: Pubkey,
) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.config_authority.key(),
        ctx.accounts.config.config_authority,
        MarketplaceError::Unauthorized
    );
    require_keys_eq!(
        ctx.accounts.new_signer.key(),
        requested,
        MarketplaceError::InvalidAuthorityRotation
    );
    require!(
        requested != Pubkey::default()
            && requested != ctx.accounts.config.authorization_signer
            && requested != ctx.accounts.config.config_authority
            && requested != ctx.accounts.config.pause_authority,
        MarketplaceError::InvalidAuthorityRotation
    );
    let old = ctx.accounts.config.authorization_signer;
    let version = bump_version(&mut ctx.accounts.config)?;
    ctx.accounts.config.authorization_signer = requested;
    emit_update(
        ctx.accounts.config.key(),
        2,
        old,
        requested,
        ctx.accounts.config_authority.key(),
        version,
    );
    Ok(())
}

pub fn rotate_config_authority(
    ctx: Context<RotateConfigAuthority>,
    requested: Pubkey,
) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.current_authority.key(),
        ctx.accounts.config.config_authority,
        MarketplaceError::Unauthorized
    );
    require_keys_eq!(
        ctx.accounts.new_authority.key(),
        requested,
        MarketplaceError::InvalidAuthorityRotation
    );
    require!(
        requested != Pubkey::default()
            && requested != ctx.accounts.config.config_authority
            && requested != ctx.accounts.config.authorization_signer
            && requested != ctx.accounts.config.pause_authority,
        MarketplaceError::InvalidAuthorityRotation
    );
    let old = ctx.accounts.config.config_authority;
    let version = bump_version(&mut ctx.accounts.config)?;
    ctx.accounts.config.config_authority = requested;
    emit_update(
        ctx.accounts.config.key(),
        3,
        old,
        requested,
        ctx.accounts.current_authority.key(),
        version,
    );
    Ok(())
}

pub fn rotate_pause_authority(ctx: Context<RotatePauseAuthority>, requested: Pubkey) -> Result<()> {
    require_keys_eq!(
        ctx.accounts.config_authority.key(),
        ctx.accounts.config.config_authority,
        MarketplaceError::Unauthorized
    );
    require_keys_eq!(
        ctx.accounts.new_authority.key(),
        requested,
        MarketplaceError::InvalidAuthorityRotation
    );
    require!(
        requested != Pubkey::default()
            && requested != ctx.accounts.config.pause_authority
            && requested != ctx.accounts.config.config_authority
            && requested != ctx.accounts.config.authorization_signer,
        MarketplaceError::InvalidAuthorityRotation
    );
    let old = ctx.accounts.config.pause_authority;
    let version = bump_version(&mut ctx.accounts.config)?;
    ctx.accounts.config.pause_authority = requested;
    emit_update(
        ctx.accounts.config.key(),
        4,
        old,
        requested,
        ctx.accounts.config_authority.key(),
        version,
    );
    Ok(())
}

fn bump_version(config: &mut Account<MarketplaceConfig>) -> Result<u32> {
    let version = config
        .config_version
        .checked_add(1)
        .ok_or(MarketplaceError::ArithmeticOverflow)?;
    config.config_version = version;
    Ok(version)
}

fn emit_update(
    config: Pubkey,
    field: u8,
    old: Pubkey,
    new: Pubkey,
    authority: Pubkey,
    config_version: u32,
) {
    emit!(MarketplaceConfigUpdated {
        config,
        field,
        old_value: old,
        new_value: new,
        authority,
        config_version
    });
}

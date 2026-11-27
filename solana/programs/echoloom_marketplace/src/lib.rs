pub mod authorization;
pub mod constants;
pub mod errors;
pub mod events;
pub mod instructions;
pub mod state;
pub mod token;

use anchor_lang::prelude::*;

pub use constants::*;
pub use errors::*;
pub use events::*;
pub use instructions::*;
pub use state::*;

declare_id!("2GKAJH8MWn8qZXB966AGDmbmZztKy5wjRVzLpPuQLjeu");

#[program]
pub mod echoloom_marketplace {
    use super::*;

    pub fn initialize_marketplace(
        ctx: Context<InitializeMarketplace>,
        args: InitializeMarketplaceArgs,
    ) -> Result<()> {
        instructions::initialize_marketplace::handle(ctx, args)
    }

    pub fn update_marketplace_config(
        ctx: Context<UpdateMarketplaceConfig>,
        new_treasury: Pubkey,
    ) -> Result<()> {
        instructions::update_config::handle(ctx, new_treasury)
    }

    pub fn rotate_authorized_signer(
        ctx: Context<RotateAuthorizedSigner>,
        new_signer: Pubkey,
    ) -> Result<()> {
        instructions::rotate_authorities::rotate_authorized_signer(ctx, new_signer)
    }

    pub fn rotate_config_authority(
        ctx: Context<RotateConfigAuthority>,
        new_authority: Pubkey,
    ) -> Result<()> {
        instructions::rotate_authorities::rotate_config_authority(ctx, new_authority)
    }

    pub fn rotate_pause_authority(
        ctx: Context<RotatePauseAuthority>,
        new_authority: Pubkey,
    ) -> Result<()> {
        instructions::rotate_authorities::rotate_pause_authority(ctx, new_authority)
    }

    pub fn pause_marketplace(ctx: Context<PauseMarketplace>) -> Result<()> {
        instructions::pause::pause(ctx)
    }

    pub fn resume_marketplace(ctx: Context<ResumeMarketplace>) -> Result<()> {
        instructions::pause::resume(ctx)
    }

    pub fn purchase(ctx: Context<Purchase>) -> Result<()> {
        instructions::purchase::handle(ctx)
    }
}

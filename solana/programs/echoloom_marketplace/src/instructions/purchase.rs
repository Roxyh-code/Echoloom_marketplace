use anchor_lang::prelude::*;
use anchor_spl::token::{Mint, Token, TokenAccount};

use crate::{
    authorization::{ed25519_verifier::verify_previous_instruction, message::AuthorizationFields},
    constants::{
        CONFIG_SEED, MAX_AUTHORIZATION_LIFETIME_SECONDS, MAX_RECIPIENTS, RECEIPT_SEED,
        RECEIPT_SPACE, RECEIPT_VERSION,
    },
    errors::MarketplaceError,
    events::PurchaseExecuted,
    state::{MarketplaceConfig, PayoutEntry, PurchaseReceipt},
};

#[derive(Accounts)]
pub struct Purchase<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,
    #[account(seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, MarketplaceConfig>,
    /// CHECK: hash seed is read from the previous verified Ed25519 message, then checked in the handler.
    #[account(mut)]
    pub receipt: UncheckedAccount<'info>,
    #[account(address = config.payment_mint)]
    pub payment_mint: Account<'info, Mint>,
    #[account(mut)]
    pub buyer_source: Account<'info, TokenAccount>,
    /// CHECK: active slot is validated as a classic SPL token account and canonical ATA; inactive slots must alias buyer_source.
    #[account(mut)]
    pub recipient_0: UncheckedAccount<'info>,
    /// CHECK: active slot is validated as a classic SPL token account and canonical ATA; inactive slots must alias buyer_source.
    #[account(mut)]
    pub recipient_1: UncheckedAccount<'info>,
    /// CHECK: active slot is validated as a classic SPL token account and canonical ATA; inactive slots must alias buyer_source.
    #[account(mut)]
    pub recipient_2: UncheckedAccount<'info>,
    #[account(address = anchor_spl::token::ID)]
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    /// CHECK: address and contents are checked by the SDK Instructions Sysvar parser.
    pub instructions_sysvar: UncheckedAccount<'info>,
    pub clock: Sysvar<'info, Clock>,
}

pub fn handle(ctx: Context<Purchase>) -> Result<()> {
    require!(
        anchor_lang::solana_program::instruction::get_stack_height()
            == anchor_lang::solana_program::instruction::TRANSACTION_LEVEL_STACK_HEIGHT,
        MarketplaceError::InvalidInstructionStackHeight
    );
    require!(
        !ctx.accounts.config.paused,
        MarketplaceError::MarketplacePaused
    );
    require!(
        ctx.accounts.config.account_version == crate::constants::CONFIG_VERSION,
        MarketplaceError::InvalidAccountVersion
    );
    require_keys_eq!(
        ctx.accounts.config.token_program,
        anchor_spl::token::ID,
        MarketplaceError::UnsupportedTokenProgram
    );
    require_keys_eq!(
        ctx.accounts.token_program.key(),
        ctx.accounts.config.token_program,
        MarketplaceError::InvalidTokenProgram
    );
    require!(
        ctx.accounts.buyer_source.owner == ctx.accounts.buyer.key()
            && ctx.accounts.buyer_source.mint == ctx.accounts.payment_mint.key()
            && ctx.accounts.payment_mint.to_account_info().owner == &anchor_spl::token::ID,
        MarketplaceError::InvalidBuyerTokenAccount
    );

    let message = verify_previous_instruction(
        &ctx.accounts.instructions_sysvar.to_account_info(),
        &ctx.accounts.config.authorization_signer,
    )?;
    let authorization = AuthorizationFields::parse(&message)?;
    require_keys_eq!(
        authorization.program_id,
        crate::ID,
        MarketplaceError::InvalidAuthorization
    );
    require_keys_eq!(
        authorization.config,
        ctx.accounts.config.key(),
        MarketplaceError::InvalidAuthorization
    );
    require_keys_eq!(
        authorization.buyer,
        ctx.accounts.buyer.key(),
        MarketplaceError::InvalidBuyer
    );
    require_keys_eq!(
        authorization.mint,
        ctx.accounts.payment_mint.key(),
        MarketplaceError::InvalidMint
    );
    require_keys_eq!(
        authorization.token_program,
        ctx.accounts.token_program.key(),
        MarketplaceError::InvalidTokenProgram
    );
    require!(
        authorization.deployment_domain_hash == ctx.accounts.config.deployment_domain_hash
            && authorization.config_version == ctx.accounts.config.config_version,
        MarketplaceError::InvalidAuthorization
    );
    require!(
        authorization.order_reference_hash != [0; 32],
        MarketplaceError::InvalidOrderReference
    );
    require!(
        authorization.product_hash != [0; 32] && authorization.nonce != [0; 32],
        MarketplaceError::InvalidAuthorization
    );
    require!(
        authorization.gross_amount > 0,
        MarketplaceError::InvalidTotalAmount
    );

    validate_payouts(&ctx, &authorization)?;
    let now = ctx.accounts.clock.unix_timestamp;
    require!(
        authorization.expires_at_unix > 0 && now < authorization.expires_at_unix,
        MarketplaceError::ExpiredAuthorization
    );
    require!(
        authorization
            .expires_at_unix
            .checked_sub(now)
            .ok_or(MarketplaceError::ArithmeticOverflow)?
            <= MAX_AUTHORIZATION_LIFETIME_SECONDS,
        MarketplaceError::AuthorizationLifetimeExceeded
    );

    let (receipt_address, receipt_bump) = Pubkey::find_program_address(
        &[RECEIPT_SEED, authorization.order_reference_hash.as_ref()],
        ctx.program_id,
    );
    require_keys_eq!(
        receipt_address,
        ctx.accounts.receipt.key(),
        MarketplaceError::InvalidPda
    );
    if ctx.accounts.receipt.owner == ctx.program_id {
        let data = ctx.accounts.receipt.try_borrow_data()?;
        let mut slice: &[u8] = &data;
        let existing = PurchaseReceipt::try_deserialize(&mut slice)
            .map_err(|_| error!(MarketplaceError::PrefundedAccountInitializationFailed))?;
        require!(
            existing.receipt_version == RECEIPT_VERSION,
            MarketplaceError::InvalidAccountVersion
        );
        return err!(MarketplaceError::PurchaseAlreadyProcessed);
    }
    require!(
        ctx.accounts.receipt.owner == &System::id()
            && ctx.accounts.receipt.data_is_empty()
            && !ctx.accounts.receipt.executable,
        MarketplaceError::PrefundedAccountInitializationFailed
    );

    let destinations = [
        &ctx.accounts.recipient_0,
        &ctx.accounts.recipient_1,
        &ctx.accounts.recipient_2,
    ];
    for (index, destination) in destinations
        .iter()
        .enumerate()
        .take(usize::from(authorization.recipient_count))
    {
        crate::token::transfers::transfer_checked(
            &ctx.accounts.token_program,
            &ctx.accounts.buyer_source,
            &ctx.accounts.payment_mint,
            &destination.to_account_info(),
            &ctx.accounts.buyer,
            authorization.recipients[index].amount,
        )
        .map_err(|_| error!(MarketplaceError::TokenTransferFailed))?;
    }

    let bump_seed = [receipt_bump];
    crate::instructions::pda_init::create_pda_account(
        &ctx.accounts.buyer.to_account_info(),
        &ctx.accounts.receipt.to_account_info(),
        &ctx.accounts.system_program.to_account_info(),
        RECEIPT_SPACE,
        &[
            RECEIPT_SEED,
            authorization.order_reference_hash.as_ref(),
            &bump_seed,
        ],
    )?;
    let receipt = PurchaseReceipt {
        receipt_version: RECEIPT_VERSION,
        bump: receipt_bump,
        buyer: authorization.buyer,
        order_reference_hash: authorization.order_reference_hash,
        product_hash: authorization.product_hash,
        mint: authorization.mint,
        gross_amount: authorization.gross_amount,
        recipient_count: authorization.recipient_count,
        recipients: authorization.recipients,
        config_version: authorization.config_version,
        created_at_unix: now,
        created_at_slot: ctx.accounts.clock.slot,
    };
    receipt
        .try_serialize(&mut &mut ctx.accounts.receipt.try_borrow_mut_data()?[..])
        .map_err(|_| error!(MarketplaceError::PrefundedAccountInitializationFailed))?;

    emit!(PurchaseExecuted {
        receipt: ctx.accounts.receipt.key(),
        order_reference_hash: authorization.order_reference_hash,
        buyer: authorization.buyer,
        mint: authorization.mint,
        gross_amount: authorization.gross_amount,
        recipient_count: authorization.recipient_count,
        config_version: authorization.config_version,
    });
    Ok(())
}

fn validate_payouts(ctx: &Context<Purchase>, authorization: &AuthorizationFields) -> Result<()> {
    let count = usize::from(authorization.recipient_count);
    require!(
        (1..=MAX_RECIPIENTS).contains(&count),
        MarketplaceError::InvalidRecipientCount
    );
    let destinations = [
        &ctx.accounts.recipient_0,
        &ctx.accounts.recipient_1,
        &ctx.accounts.recipient_2,
    ];
    let mut sum = 0u128;
    let mut previous: Option<Pubkey> = None;
    for (index, destination) in destinations.iter().enumerate() {
        let destination = *destination;
        let payout: PayoutEntry = authorization.recipients[index];
        if index >= count {
            require!(
                payout.owner == Pubkey::default() && payout.amount == 0,
                MarketplaceError::InvalidPayoutAmounts
            );
            require!(
                destination.key() == ctx.accounts.buyer_source.key(),
                MarketplaceError::InvalidRecipientAccount
            );
            continue;
        }
        require!(
            payout.owner != Pubkey::default() && payout.amount > 0,
            MarketplaceError::InvalidPayoutAmounts
        );
        require!(
            payout.owner != ctx.accounts.buyer.key(),
            MarketplaceError::BuyerCannotReceivePayout
        );
        if let Some(prior) = previous {
            require!(prior != payout.owner, MarketplaceError::DuplicateRecipient);
            require!(
                prior.as_ref() < payout.owner.as_ref(),
                MarketplaceError::UnsortedRecipients
            );
        }
        previous = Some(payout.owner);
        sum = sum
            .checked_add(u128::from(payout.amount))
            .ok_or(MarketplaceError::ArithmeticOverflow)?;
        require_keys_eq!(
            *destination.owner,
            anchor_spl::token::ID,
            MarketplaceError::InvalidRecipientAccount
        );
        require!(
            !destination.executable,
            MarketplaceError::InvalidRecipientAccount
        );
        let destination_data = destination.try_borrow_data()?;
        let mut destination_bytes: &[u8] = &destination_data;
        let token_account = TokenAccount::try_deserialize(&mut destination_bytes)
            .map_err(|_| error!(MarketplaceError::InvalidRecipientAccount))?;
        require!(
            token_account.owner == payout.owner
                && token_account.mint == ctx.accounts.payment_mint.key(),
            MarketplaceError::InvalidRecipientAccount
        );
        let expected_ata =
            anchor_spl::associated_token::get_associated_token_address_with_program_id(
                &payout.owner,
                &ctx.accounts.payment_mint.key(),
                &anchor_spl::token::ID,
            );
        require_keys_eq!(
            *destination.key,
            expected_ata,
            MarketplaceError::InvalidRecipientAccount
        );
        require!(
            *destination.key != ctx.accounts.buyer_source.key(),
            MarketplaceError::InvalidRecipientAccount
        );
    }
    require!(
        sum == u128::from(authorization.gross_amount),
        MarketplaceError::InvalidTotalAmount
    );
    Ok(())
}

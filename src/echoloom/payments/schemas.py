from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: UUID
    buyer_wallet: str = Field(min_length=32, max_length=44)


class PayoutLine(BaseModel):
    wallet: str
    amount_minor_units: int


class QuoteResponse(BaseModel):
    order_id: UUID
    expires_at: str
    program_id: str
    mint: str
    decimals: int = 6
    amount_minor_units: int
    payout_lines: list[PayoutLine]
    config_pda: str
    receipt_pda: str
    signer_pubkey: str
    authorization_message_b64: str
    authorization_signature_b64: str

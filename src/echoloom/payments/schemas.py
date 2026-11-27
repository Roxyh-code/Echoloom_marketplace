from typing import Literal
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


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    tx_signature: str = Field(min_length=64, max_length=88)


class SceneAllowance(BaseModel):
    used: int
    limit: int


class VerifyResponse(BaseModel):
    status: Literal["pending", "paid", "rejected"]
    reason: str | None = None
    scene_allowance: SceneAllowance


class WalletChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wallet: str = Field(min_length=32, max_length=44)


class WalletChallengeResponse(BaseModel):
    challenge_id: UUID
    message: str
    expires_at: str


class WalletVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    signature_b64: str = Field(min_length=88, max_length=88)


class WalletStatus(BaseModel):
    wallet: str | None = None
    verified: bool = False

"""Authenticated payment and buyer-wallet endpoints."""
from fastapi import Request

from .quote import create_quote
from .schemas import QuoteRequest, QuoteResponse, VerifyRequest, VerifyResponse
from .verification import verify_order
from .schemas import WalletChallengeRequest, WalletChallengeResponse, WalletVerifyRequest, WalletStatus
from .wallet import create_challenge, verify_challenge, verified_wallet, require_owner


def register_payments(app, factory, settings):
    @app.post("/api/payments/quote", response_model=QuoteResponse)
    def quote(body: QuoteRequest, request: Request):
        with factory() as db:
            owner = getattr(request.state, "user_id", None)
            return create_quote(db, settings, owner, body, verified_wallet(db, owner))

    @app.post("/api/payments/verify", response_model=VerifyResponse)
    def verify(body: VerifyRequest, request: Request):
        with factory() as db:
            return verify_order(db, settings, getattr(request.state, "user_id", None), body)


    @app.get("/api/payments/wallet", response_model=WalletStatus)
    def wallet_status(request: Request):
        owner = getattr(request.state, "user_id", None)
        require_owner(owner)
        with factory() as db:
            wallet = verified_wallet(db, owner)
            return {"wallet": wallet, "verified": bool(wallet)}

    @app.post("/api/payments/wallet/challenge", response_model=WalletChallengeResponse)
    def wallet_challenge(body: WalletChallengeRequest, request: Request):
        with factory() as db:
            return create_challenge(db, settings, getattr(request.state, "user_id", None), body.wallet)

    @app.post("/api/payments/wallet/verify", response_model=WalletStatus)
    def wallet_verify(body: WalletVerifyRequest, request: Request):
        with factory() as db:
            return verify_challenge(db, settings, getattr(request.state, "user_id", None), body)


    @app.get("/api/payments/readiness/{scene_id}")
    def readiness(scene_id: str, request: Request):
        from fastapi import HTTPException
        from ..db import RehearsalScene
        from .readiness import checkout_readiness

        owner = getattr(request.state, "user_id", None)
        require_owner(owner)
        with factory() as db:
            scene = db.get(RehearsalScene, scene_id)
            if not scene or scene.owner_id != owner:
                raise HTTPException(404, "Scene not found")
            ready, reason = checkout_readiness(db, settings, scene)
            return {"available": ready, "reason": reason}


    @app.get("/api/payments/creator/earnings")
    def earnings(request: Request):
        from .earnings import creator_earnings
        owner = getattr(request.state, "user_id", None)
        require_owner(owner)
        with factory() as db:
            return creator_earnings(db, owner)

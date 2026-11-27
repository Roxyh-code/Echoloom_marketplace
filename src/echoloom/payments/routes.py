"""Payment API; wallet binding is deliberately fail-closed until implemented."""
from fastapi import Request

from .quote import create_quote
from .schemas import QuoteRequest, QuoteResponse


def register_payments(app, factory, settings):
    @app.post("/api/payments/quote", response_model=QuoteResponse)
    def quote(body: QuoteRequest, request: Request):
        # Future wallet binding registers this trusted server-side resolver.
        # Never accept a wallet as verified based on request JSON or headers.
        resolver = getattr(app.state, "verified_buyer_wallet", None)
        with factory() as db:
            owner = getattr(request.state, "user_id", None)
            wallet = resolver(db, request) if resolver and owner else None
            return create_quote(db, settings, owner, body, wallet)

# Echoloom Marketplace — Dev3pack 2026

**Phase 1: migration baseline (in progress).** A mobile-first, two-character interactive story application built on the existing Echoloom rehearsal engine. The marketplace and Solana payment flow will be implemented in subsequent stages.

## Provenance

Source: [Roxyh-code/Echoloom_V2](https://github.com/Roxyh-code/Echoloom_V2), pre-hackathon code. Files transferred from that repository must be treated as **pre-existing work**, not as functionality originally created during Dev3pack. Refer to `docs/MIGRATION.md` for an inventory and the distinction between copied and newly authored features.

## MVP workflow

Discover creator-authorized characters → cast exactly two → write a scene prompt → get a quote → make a verified Solana Devnet payment → access an AI-generated, interactive scene → save the result.

The current extraction step is limited to the pre-existing **character creation, portrait generation and rehearsal engine**. Public listings, wallet sign-in, quotes, orders, payment verification, payouts and entitlement enforcement **do not exist yet**.

## Stack

- Next.js 16 / React 19 / TypeScript front end in `web/`
- FastAPI / SQLAlchemy / Alembic / LangGraph backend in `src/echoloom/`

## Safety and rights

Do not commit `.env`, `work/`, databases, character histories, private credentials or wallet private keys. Public marketplace listings must only feature original or properly licensed characters and disclose only publication-safe fields.

## Status

This README initializes the new repository. The Stage 1 source extraction and smoke-test report will be committed separately.

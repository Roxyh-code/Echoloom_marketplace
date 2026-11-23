"use client";

import type { CastSource } from "./rehearsal-api";
import type { MarketplaceListing } from "./marketplace-api";

/** Only public listing IDs or owner-only character IDs are persisted in a cast. */
export type CastChoice = {
  key: string;
  source: CastSource;
  name: string;
  image: string | null;
};

const STORAGE_KEY = "echoloom.marketplace.cast.v1";

export function listingChoice(record: MarketplaceListing): CastChoice {
  return {
    key: "listing:" + record.listing_id,
    source: {
      source: "listing",
      listing_id: record.listing_id,
      expected_revision: record.revision,
    },
    name: record.name,
    image: record.cover_image_url,
  };
}

export function privateChoice(characterId: string, name: string, image: string | null): CastChoice {
  return {
    key: "private:" + characterId,
    source: { source: "private", character_id: characterId },
    name,
    image,
  };
}

function validChoice(input: unknown): input is CastChoice {
  if (!input || typeof input !== "object") return false;
  const item = input as Record<string, unknown>;
  if (typeof item.name !== "string" || !item.name || item.name.length > 100) return false;
  if (item.image !== null && typeof item.image !== "string") return false;
  if (!item.source || typeof item.source !== "object") return false;
  const source = item.source as Record<string, unknown>;
  if (source.source === "private") {
    return typeof source.character_id === "string" &&
      item.key === "private:" + source.character_id;
  }
  return source.source === "listing" &&
    typeof source.listing_id === "string" &&
    Number.isInteger(source.expected_revision) &&
    Number(source.expected_revision) >= 1 &&
    item.key === "listing:" + source.listing_id;
}

export function readCast(): CastChoice[] {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    const selected = parsed.filter(validChoice);
    return selected.filter((item, index) => selected.findIndex((v) => v.key === item.key) === index).slice(0, 2);
  } catch {
    return [];
  }
}

export function saveCast(cast: CastChoice[]): void {
  try {
    if (cast.length) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(cast.slice(0, 2)));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Selection still works in memory when device storage is disabled.
  }
}

/** A new third character replaces the oldest unless a specific slot was selected. */
export function addCast(cast: CastChoice[], choice: CastChoice, replacement: number | null = null): CastChoice[] {
  const existing = cast.findIndex((item) => item.key === choice.key);
  if (existing !== -1) return cast;
  if (replacement !== null && replacement >= 0 && replacement < cast.length) {
    return cast.map((item, i) => i === replacement ? choice : item);
  }
  return cast.length < 2 ? [...cast, choice] : [cast[1], choice];
}

export function addPublishedToSavedCast(listing: MarketplaceListing): void {
  saveCast(addCast(readCast(), listingChoice(listing)));
}

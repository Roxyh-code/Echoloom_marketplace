/**
 * Marketplace Listing API client.
 *
 * Matches the FastAPI contracts in:
 *   src/echoloom/marketplace_schemas.py
 *   src/echoloom/marketplace_routes.py
 *
 * Use the existing Next.js same-origin /api rewrite. Do not put wallet or
 * account IDs in a publish request: the backend obtains identity from a
 * server-verified session. Wallet Sign-In is not implemented in this step.
 */

export type MarketplaceListing = {
  listing_id: string;
  revision: number;
  name: string;
  short_description: string;
  tags: string[];
  public_personality: string[];
  creator_display_name: string;
  cover_image_url: string | null;
};

export type ListingPublishInput = {
  character_id: string;
  name: string;
  short_description: string;
  tags?: string[];
  public_personality?: string[];
  rights_basis: "original" | "licensed";
  rights_confirmed: true;
  enable_earnings?: boolean;
};

export type OwnedListing = {
  listing_id: string;
  character_id: string;
  status: "published" | "unpublished";
  latest_revision: number;
  monetization_enabled?: boolean;
};

/** Owner-only editing data, including currently unpublished snapshots. */
export type OwnedListingDetail = OwnedListing & {
  name: string;
  short_description: string;
  tags: string[];
  public_personality: string[];
  rights_basis: "original" | "licensed";
};

export class MarketplaceApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "MarketplaceApiError";
  }
}

const BASE = "/api/marketplace/listings";

async function requestMarketplace<T>(
  path: string,
  options: RequestInit = {},
  promptForAuth = true,
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!response.ok) {
    if (promptForAuth && response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("echoloom-auth-required"));
    }
    const data: unknown = await response.json().catch(() => null);
    const detail =
      data && typeof data === "object" && "detail" in data
        ? data.detail
        : null;
    const message =
      typeof detail === "string"
        ? detail
        : response.status === 422
          ? "Invalid listing data. Please check your fields."
          : `Marketplace request failed (HTTP ${response.status}).`;
    throw new MarketplaceApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Public: no login required. limit is between 1 and 100 (backend-enforced). */
export function listPublishedListings(
  limit = 50,
  signal?: AbortSignal,
): Promise<MarketplaceListing[]> {
  return requestMarketplace<MarketplaceListing[]>(
    `${BASE}?limit=${encodeURIComponent(String(limit))}`,
    { signal },
  );
}

/** Public: one currently published listing; unpublished listings return 404. */
export function getPublishedListing(
  listingId: string,
  signal?: AbortSignal,
): Promise<MarketplaceListing> {
  return requestMarketplace<MarketplaceListing>(
    `${BASE}/${encodeURIComponent(listingId)}`,
    { signal },
  );
}

/** Private: the logged-in creator's own listing snapshots, no wallet fields. */
export function listOwnedListings(signal?: AbortSignal): Promise<OwnedListingDetail[]> {
  // Optional enrichment for Discover. An anonymous visitor can still browse
  // public listings without opening a login dialog.
  return requestMarketplace<OwnedListingDetail[]>("/api/marketplace/my-listings", { signal }, false);
}

/** Private: authenticated character owner only; no payout wallet needed. */
export function publishCharacterListing(
  input: ListingPublishInput,
): Promise<OwnedListing> {
  return requestMarketplace<OwnedListing>(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

/** Private: ownership is verified by the backend. */
export function getOwnedListing(listingId: string): Promise<OwnedListing> {
  return requestMarketplace<OwnedListing>(
    `${BASE}/${encodeURIComponent(listingId)}/owner`,
  );
}

/** Private: prevent future public discovery without deleting saved revisions. */
export function unpublishCharacterListing(listingId: string): Promise<OwnedListing> {
  return requestMarketplace<OwnedListing>(
    `${BASE}/${encodeURIComponent(listingId)}/unpublish`,
    { method: "POST" },
  );
}

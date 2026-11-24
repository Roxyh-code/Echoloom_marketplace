"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getPublishedListing,
  type MarketplaceListing,
  MarketplaceApiError,
} from "@/components/marketplace-api";
import "../marketplace.css";
import { MobileBottomNav } from "@/components/mobile-bottom-nav";
import { addPublishedToSavedCast } from "@/components/marketplace-casting";
import { CharacterDetailArticle } from "@/components/marketplace-character-detail";

/** Public listing preview: never load or render the private Character profile. */
export default function PublicListingPage() {
  const params = useParams<{ listingId: string }>();
  const router = useRouter();
  const listingId = params.listingId;
  const [listing, setListing] = useState<MarketplaceListing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setListing(null);
    getPublishedListing(listingId, controller.signal)
      .then((record) => {
        if (!controller.signal.aborted) setListing(record);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          cause instanceof MarketplaceApiError && cause.status === 404
            ? "This character is no longer publicly listed."
            : "Could not load this public listing. Please try again.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [listingId]);

  return (
    <main className="em-app em-detail-page">
      <div className="em-page">
        <header className="em-header">
          <Link className="em-brand" href="/marketplace" aria-label="Echoloom Discover home">
            <img className="em-brand-icon" src="/echoloom-gothic-mark.svg" alt="" aria-hidden="true" />
            <span>Echoloom<span className="em-brand-dot">.</span></span>
          </Link>
          <Link href="/marketplace" style={{ color: "#CBB7FF", fontSize: 13, fontWeight: 650 }}>
            ← Discover
          </Link>
        </header>

        {loading ? (
          <section className="em-empty" role="status" style={{ marginTop: 28 }}>
            <h1>Opening the character…</h1>
          </section>
        ) : error ? (
          <section className="em-empty" style={{ marginTop: 28 }}>
            <h1 style={{ fontSize: 22 }}>Listing unavailable</h1>
            <p role="alert">{error}</p>
            <Link href="/marketplace">Back to Discover →</Link>
          </section>
        ) : listing ? (
          <CharacterDetailArticle
            name={listing.name}
            description={listing.short_description}
            image={listing.cover_image_url}
            source="public"
            revision={listing.revision}
            creator={listing.creator_display_name}
            tags={listing.tags}
            traits={listing.public_personality}
            onAddToCast={() => {
              addPublishedToSavedCast(listing);
              router.push("/marketplace");
            }}
          />
        ) : null}
      </div>
      <MobileBottomNav active="discover" />
    </main>
  );
}

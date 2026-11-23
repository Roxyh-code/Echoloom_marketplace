"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getPublishedListing,
  type MarketplaceListing,
  MarketplaceApiError,
} from "@/components/marketplace-api";
import "../marketplace.css";
import { MobileBottomNav } from "@/components/mobile-bottom-nav";

/** Public listing preview: never load or render the private Character profile. */
export default function PublicListingPage() {
  const params = useParams<{ listingId: string }>();
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
          <article style={{ padding: "24px 0 40px" }}>
            <span className="em-kicker">PUBLIC CHARACTER · REVISION {listing.revision}</span>
            <div style={{ display: "flex", gap: 18, marginTop: 18, alignItems: "flex-start" }}>
              <div style={{
                width: "42%", flexShrink: 0, aspectRatio: "2 / 3",
                borderRadius: 12, overflow: "hidden", background: "#faf9fd",
                display: "grid", placeItems: "center",
              }}>
                {listing.cover_image_url ? (
                  <img
                    src={listing.cover_image_url}
                    alt={"Portrait of " + listing.name}
                    style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center 32%" }}
                  />
                ) : (
                  <span style={{ fontSize: 68, fontWeight: 650, color: "#54408c" }}>{listing.name.slice(0, 1)}</span>
                )}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <h1 style={{ margin: "0 0 12px", fontSize: 27, lineHeight: 1.15, overflowWrap: "anywhere" }}>
                  {listing.name}
                </h1>
                <p style={{ fontSize: 12, color: "#7a7a7a" }}>Created by {listing.creator_display_name}</p>
                <p style={{ marginTop: 17, color: "#525252", lineHeight: 1.6, overflowWrap: "anywhere" }}>
                  {listing.short_description}
                </p>
              </div>
            </div>

            {listing.tags.length > 0 && (
              <section style={{ marginTop: 27 }} aria-label="Story tags">
                <h2 style={{ fontSize: 14, marginBottom: 12 }}>Story tags</h2>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {listing.tags.map((tag) => (
                    <span key={tag} style={{ border: "1px solid #e8e8e8", padding: "6px 10px", borderRadius: 20, fontSize: 12 }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {listing.public_personality.length > 0 && (
              <section style={{ marginTop: 26 }} aria-label="Public personality traits">
                <h2 style={{ fontSize: 14, marginBottom: 12 }}>Personality</h2>
                <p style={{ color: "#525252", fontSize: 13 }}>{listing.public_personality.join(" · ")}</p>
              </section>
            )}

            <Link href="/marketplace" className="em-hero-link" style={{ marginTop: 24 }}>
              ← Explore more characters
            </Link>
          </article>
        ) : null}
      </div>
      <MobileBottomNav active="discover" />
    </main>
  );
}

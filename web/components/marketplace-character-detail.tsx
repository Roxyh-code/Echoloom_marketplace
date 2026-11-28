"use client";

import Link from "next/link";

type CharacterDetailProps = {
  name: string;
  description: string;
  image: string | null;
  source: "public" | "private";
  revision: number;
  creator?: string;
  tags?: string[];
  traits?: string[];
  appearance?: Record<string, string>;
  backstory?: string;
  onAddToCast: () => void;
  researchSources?: React.ReactNode;
};

/** Shared presentation for public Listings and owner-only private Characters.
 * Only pass Listing-safe published fields to the public detail route.
 */
export function CharacterDetailArticle({
  name, description, image, source, revision, creator, tags = [], traits = [],
  appearance, backstory, onAddToCast, researchSources,
}: CharacterDetailProps) {
  const appearanceEntries = Object.entries(appearance || {})
    .filter(([, detail]) => typeof detail === "string" && detail.trim());
  return (
    <article className="em-character-article">
      <span className="em-kicker">
        {source === "public" ? "PUBLIC CHARACTER" : "YOUR PRIVATE CHARACTER"} · VERSION {revision}
      </span>
      <div className="em-character-intro">
        <div className="em-detail-portrait">
          {image ? (
            <img src={image} alt={"Portrait of " + name} />
          ) : (
            <span className="em-cover-monogram">{name.slice(0, 1)}</span>
          )}
        </div>
        <div className="em-character-description">
          <h1>{name}</h1>
          <p className="em-detail-creator">
            {source === "public" ? "Created by " + (creator || "Echoloom creator") : "Only you can view this profile"}
          </p>
          <p className="em-detail-summary">{description}</p>
        </div>
      </div>
      {source==="private" && researchSources}
      {tags.length > 0 && (
        <section className="em-detail-section" aria-label="Story tags">
          <h2>Story tags</h2>
          <div className="em-detail-tags">
            {tags.map((tag) => <span key={tag}>{tag}</span>)}
          </div>
        </section>
      )}
      {traits.length > 0 && (
        <section className="em-detail-section" aria-label="Character personality">
          <h2>Personality</h2>
          <p>{traits.join(" · ")}</p>
        </section>
      )}
      {source === "private" && appearanceEntries.length > 0 && (
        <section className="em-detail-section" aria-label="Character appearance">
          <h2>Appearance</h2>
          <p>{appearanceEntries.map(([feature, detail]) => feature + ": " + detail).join(" · ")}</p>
        </section>
      )}
      {source === "private" && backstory && (
        <section className="em-detail-section" aria-label="Character background">
          <h2>Background</h2>
          <p>{backstory}</p>
        </section>
      )}
      <div className="em-detail-actions" aria-label="Character actions">
        <button type="button" className="em-detail-button" onClick={onAddToCast}>
          <span>Add to cast</span><span aria-hidden="true" className="em-detail-button-arrow">→</span>
        </button>
        <Link href="/marketplace" className="em-detail-button">
          <span>Explore more characters</span><span aria-hidden="true" className="em-detail-button-arrow">→</span>
        </Link>
      </div>
    </article>
  );
}

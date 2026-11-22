"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import type { Character } from "@/components/api";
import { rehearsal } from "@/components/rehearsal-api";
import {
  MarketplaceApiError,
  publishCharacterListing,
  type OwnedListing,
} from "@/components/marketplace-api";

const accent = "#54408c";

function parseLabels(text: string, label: string, maximum: number): string[] {
  const values = text.split(",").map((value) => value.trim()).filter(Boolean);
  if (values.length > maximum) {
    throw new Error(`${label}: use at most ${maximum} items.`);
  }
  if (values.some((value) => value.length > 40)) {
    throw new Error(`${label}: each item must be at most 40 characters.`);
  }
  if (new Set(values.map((value) => value.toLocaleLowerCase())).size !== values.length) {
    throw new Error(`${label}: remove duplicate items.`);
  }
  return values;
}

export default function PublishCharacterPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [characterId, setCharacterId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [traitsText, setTraitsText] = useState("");
  const [rightsBasis, setRightsBasis] = useState<"original" | "licensed">("original");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<OwnedListing | null>(null);

  function chooseCharacter(character: Character) {
    setCharacterId(character.id);
    setName(character.profile.name.slice(0, 80));
    setDescription(character.profile.short_description.slice(0, 320));
    // Public details are explicitly reviewed; do not copy private backstory.
    setTagsText("");
    setTraitsText("");
    setRightsConfirmed(false);
    setRightsBasis("original");
    setError("");
    setResult(null);
  }

  useEffect(() => {
    let active = true;
    rehearsal<Character[]>("/characters")
      .then((records) => {
        if (!active) return;
        setCharacters(records);
        const requested = new URLSearchParams(window.location.search).get("character");
        const chosen = records.find((c) => c.id === requested) ?? records[0];
        if (chosen) chooseCharacter(chosen);
      })
      .catch((cause: unknown) => {
        if (active) setLoadError(cause instanceof Error ? cause.message : "Unable to load your characters.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const selected = useMemo(
    () => characters.find((character) => character.id === characterId) ?? null,
    [characters, characterId],
  );
  const portrait = selected?.current_image_id
    ? `/api/characters/${selected.id}/images/${selected.current_image_id}/file`
    : null;

  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || submitting) return;
    setError("");
    setResult(null);
    try {
      if (!name.trim() || !description.trim()) throw new Error("Name and description are required.");
      if (!rightsConfirmed) throw new Error("Confirm your publishing rights first.");
      const tags = parseLabels(tagsText, "Tags", 8);
      const publicPersonality = parseLabels(traitsText, "Public traits", 6);
      setSubmitting(true);
      const listing = await publishCharacterListing({
        character_id: selected.id,
        name: name.trim(),
        short_description: description.trim(),
        tags,
        public_personality: publicPersonality,
        rights_basis: rightsBasis,
        rights_confirmed: true,
      });
      setResult(listing);
    } catch (cause: unknown) {
      if (cause instanceof MarketplaceApiError) {
        if (cause.status === 401) {
          setError("Please sign in to your Echoloom account before publishing.");
        } else if (cause.status === 404) {
          setError("This character is not available in your account. Choose one of your own characters.");
        } else if (cause.status === 409) {
          setError(cause.message + " Please refresh the page and try again.");
        } else {
          setError(cause.message);
        }
      } else {
        setError(cause instanceof Error ? cause.message : "Publication failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={{ maxWidth: 700, margin: "0 auto", padding: "28px 20px 90px" }}>
      <nav style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 24 }}>
        <Link href="/marketplace" style={{ color: accent, fontWeight: 650 }}>← Marketplace</Link>
        <Link href="/rehearsal?view=characters" style={{ color: accent }}>My characters</Link>
      </nav>

      <p style={{ color: accent, fontSize: 12, fontWeight: 700, letterSpacing: 1.8 }}>CREATOR STUDIO</p>
      <h1 style={{ margin: "7px 0 8px" }}>Publish a character</h1>
      <p style={{ color: "#6b6473", marginBottom: 22 }}>
        Choose one of your characters and review exactly what other people will see.
        Private backstory, prompts and memories are never included in this form.
      </p>

      <div className="notice" role="note" style={{ marginBottom: 22 }}>
        <strong>No wallet needed to publish.</strong> Your character will appear in the public
        Marketplace after you confirm your publishing rights. Monetization is separate:
        connecting and verifying a Solana payout wallet will be required before your
        character can earn revenue from paid scenes.
      </div>

      {loadError && <p className="error" role="alert">{loadError}</p>}
      {loading ? (
        <p>Loading your characters…</p>
      ) : characters.length === 0 ? (
        <section className="panel">
          <p>You do not have a private character to publish yet.</p>
          <Link className="button primary" href="/characters/new" style={{ marginTop: 14 }}>Create a character</Link>
        </section>
      ) : (
        <form className="panel" onSubmit={(event) => void publish(event)}>
          <label htmlFor="listing-character">Character</label>
          <select
            id="listing-character"
            value={characterId}
            onChange={(event) => {
              const character = characters.find((item) => item.id === event.target.value);
              if (character) chooseCharacter(character);
            }}
            required
            style={{ marginBottom: 20 }}
          >
            {characters.map((character) => (
              <option value={character.id} key={character.id}>{character.profile.name}</option>
            ))}
          </select>

          <section aria-label="Listing preview" style={{ display: "flex", gap: 17, alignItems: "center", padding: 14, background: "#faf8fd", borderRadius: 12, marginBottom: 24 }}>
            <div style={{ width: 92, height: 130, overflow: "hidden", flexShrink: 0, borderRadius: 9, background: "#eae5f2", display: "grid", placeItems: "center" }}>
              {portrait ? (
                <img src={portrait} alt={`Portrait of ${selected?.profile.name ?? "character"}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              ) : (
                <span style={{ fontSize: 34, color: accent }}>{name.slice(0, 1)}</span>
              )}
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{ fontSize: 11, color: accent, fontWeight: 700 }}>PUBLIC LISTING PREVIEW</p>
              <h2 style={{ margin: "7px 0", fontSize: 22, overflowWrap: "anywhere" }}>{name || "Untitled character"}</h2>
              <p style={{ color: "#696570", fontSize: 13, overflowWrap: "anywhere" }}>{description || "No public description yet."}</p>
            </div>
          </section>

          <label htmlFor="listing-name">Public name</label>
          <input id="listing-name" value={name} onChange={(event) => setName(event.target.value)} minLength={1} maxLength={80} required style={{ marginBottom: 18 }} />

          <label htmlFor="listing-description">Public description</label>
          <textarea id="listing-description" value={description} onChange={(event) => setDescription(event.target.value)} minLength={1} maxLength={320} required rows={3} style={{ marginBottom: 5 }} />
          <p className="small muted" style={{ textAlign: "right", marginBottom: 18 }}>{description.length}/320</p>

          <label htmlFor="listing-tags">Tags (comma-separated, maximum 8)</label>
          <input id="listing-tags" value={tagsText} onChange={(event) => setTagsText(event.target.value)} placeholder="Mystery, Romance, Fantasy" style={{ marginBottom: 18 }} />

          <label htmlFor="listing-traits">Public personality traits (comma-separated, maximum 6)</label>
          <input id="listing-traits" value={traitsText} onChange={(event) => setTraitsText(event.target.value)} placeholder="Determined, Reserved, Loyal" style={{ marginBottom: 18 }} />

          <label htmlFor="rights-basis">Publishing rights</label>
          <select id="rights-basis" value={rightsBasis} onChange={(event) => setRightsBasis(event.target.value as "original" | "licensed")} style={{ marginBottom: 16 }}>
            <option value="original">I created this original character</option>
            <option value="licensed">I have permission to publicly share this character and its artwork</option>
          </select>

          <label style={{ display: "flex", alignItems: "flex-start", gap: 10, lineHeight: 1.5, marginBottom: 16 }}>
            <input type="checkbox" checked={rightsConfirmed} onChange={(event) => setRightsConfirmed(event.target.checked)} required style={{ width: 18, height: 18, flexShrink: 0, marginTop: 2 }} />
            <span>I confirm I have the rights to publicly share this character and its artwork. Publishing makes the preview details and current portrait visible to anyone who opens the Marketplace.</span>
          </label>

          <div style={{ padding: "13px 14px", background: "#f7f5fb", borderRadius: 10, margin: "18px 0 20px", fontSize: 13 }}>
            <strong>Listing:</strong> Free to publish; public browsing only for now.<br />
            <strong>Monetization:</strong> Disabled until you verify a Solana payout wallet.<br />
            <strong>Future paid packs:</strong> Platform-set at 1 test USDC; 45% to each creator and 10% to the platform.
          </div>

          {error && <p className="error" role="alert">{error}</p>}
          {result && (
            <div role="status" style={{ padding: 14, border: "1px solid #b7d8bb", background: "#f1faf3", borderRadius: 10, marginBottom: 18 }}>
              <strong>Published successfully.</strong> Your listing is public (revision {result.latest_revision}).<br />
              <span style={{ display: "block", marginTop: 5, fontSize: 12 }}>Paid scenes are not enabled until you complete wallet verification later.</span>
              <Link href="/marketplace" style={{ display: "inline-block", marginTop: 10, color: accent, textDecoration: "underline" }}>View Marketplace → choose Published</Link>
            </div>
          )}
          <button className="button primary full" type="submit" disabled={submitting || !selected || !rightsConfirmed}>
            {submitting ? "Submitting…" : "Publish to Marketplace"}
          </button>
          <p className="form-note">The server verifies your signed-in account and ownership of this character. No wallet or creator approval is needed to publish.</p>
        </form>
      )}
    </main>
  );
}

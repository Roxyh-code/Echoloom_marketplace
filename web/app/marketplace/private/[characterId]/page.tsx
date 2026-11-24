"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, portraitUrl, type Character } from "@/components/api";
import { CharacterDetailArticle } from "@/components/marketplace-character-detail";
import { addCast, privateChoice, readCast, saveCast } from "@/components/marketplace-casting";
import { MobileBottomNav } from "@/components/mobile-bottom-nav";
import "../../marketplace.css";

/** Authenticated owner-only view; never use the public Listing endpoint for this. */
export default function PrivateCharacterDetailPage() {
  const params = useParams<{ characterId: string }>();
  const router = useRouter();
  const characterId = params.characterId;
  const [character, setCharacter] = useState<Character | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setCharacter(null);
    api<Character>("/characters/" + encodeURIComponent(characterId))
      .then((item) => { if (active) setCharacter(item); })
      .catch(() => {
        if (active) setError("This private character is unavailable in your library.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [characterId]);

  function addToCast() {
    if (!character) return;
    const choice = privateChoice(character.id, character.profile.name, portraitUrl(character));
    saveCast(addCast(readCast(), choice));
    router.push("/marketplace");
  }

  return (
    <main className="em-app em-detail-page">
      <div className="em-page">
        <header className="em-header">
          <Link className="em-brand" href="/marketplace" aria-label="Echoloom Discover home">
            <img className="em-brand-icon" src="/echoloom-gothic-mark.svg" alt="" aria-hidden="true" />
            <span>Echoloom<span className="em-brand-dot">.</span></span>
          </Link>
          <Link href="/marketplace" className="em-detail-back">← Discover</Link>
        </header>
        {loading ? (
          <section className="em-empty" role="status" style={{ marginTop: 28 }}>
            <h1>Opening your character…</h1>
          </section>
        ) : error ? (
          <section className="em-empty" style={{ marginTop: 28 }}>
            <h1>Character unavailable</h1>
            <p role="alert">{error}</p>
            <Link href="/marketplace">Back to Discover →</Link>
          </section>
        ) : character ? (
          <CharacterDetailArticle
            name={character.profile.name}
            description={character.profile.short_description || character.original_description}
            image={portraitUrl(character)}
            source="private"
            revision={character.profile_version}
            traits={character.profile.personality?.core_traits || []}
            appearance={character.profile.appearance}
            backstory={character.profile.backstory}
            onAddToCast={addToCast}
          />
        ) : null}
      </div>
      <MobileBottomNav active="discover" />
    </main>
  );
}

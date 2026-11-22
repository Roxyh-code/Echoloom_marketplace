import Link from "next/link";
import { notFound } from "next/navigation";
import { findPlaceholderCharacter } from "@/components/marketplace-placeholders";
import "../../marketplace.css";

/** Static preview: deliberately does not look up a Listing or unlock rehearsal. */
export default async function CharacterPreviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const character = findPlaceholderCharacter(id);
  if (!character) notFound();
  return (
    <main className="em-app em-detail-page">
      <div className="em-page">
        <header className="em-header">
          <Link className="em-brand" href="/marketplace" aria-label="Echoloom Discover home">
            <img className="em-brand-icon" src="/echoloom-gothic-mark.svg" alt="" aria-hidden="true" />
            <span>Echoloom<span className="em-brand-dot">.</span></span>
          </Link>
          <Link href="/marketplace" style={{ color: "#CBB7FF", fontSize: 13, fontWeight: 650 }}>← Discover</Link>
        </header>
        <article style={{ padding: "24px 0 40px" }}>
          <div style={{ display: "flex", gap: 18, alignItems: "flex-start" }}>
            <div style={{
              width: "42%", flexShrink: 0, aspectRatio: "2 / 3", borderRadius: 12,
              overflow: "hidden", background: "#211c2c",
            }}>
              <img
                src={character.image}
                alt={"Portrait of " + character.name}
                style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center 32%" }}
              />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h1 style={{ margin: "0 0 12px", fontSize: 27, lineHeight: 1.15, overflowWrap: "anywhere" }}>
                {character.name}
              </h1>
              <p style={{ color: "#bcb2ce", lineHeight: 1.65, overflowWrap: "anywhere" }}>
                {character.description}
              </p>
            </div>
          </div>
          <Link href="/marketplace" className="em-hero-link" style={{ marginTop: 24 }}>← Discover characters</Link>
        </article>
      </div>
      <nav className="em-bottom-nav" aria-label="Primary navigation">
        <Link href="/marketplace" aria-current="page"><span>Discover</span></Link>
        <Link href="/characters/new"><span>Create character</span></Link>
      </nav>
    </main>
  );
}

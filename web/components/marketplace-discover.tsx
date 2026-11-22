"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Character, Scene } from "./rehearsal-api";
import { blankSetup, operation, rehearsal } from "./rehearsal-api";
import { listOwnedListings, listPublishedListings, type MarketplaceListing, type OwnedListingDetail } from "./marketplace-api";

type ShelfItem = {
  id: string;
  name: string;
  description: string;
  image: string | null;
  kind: "sample" | "mine" | "concept" | "published";
  listingId?: string;
  creator?: string;
  tags?: string[];
};

const samples: ShelfItem[] = [
  {
    id: "sample-mira",
    name: "Mira",
    description: "A quiet archivist with a story left unfinished.",
    image: "/portraits/mira.webp",
    kind: "sample",
  },
  {
    id: "sample-leo",
    name: "Leo",
    description: "A wanderer whose past won't stay buried.",
    image: "/portraits/leo.webp",
    kind: "sample",
  },
  {
    id: "concept-vesper",
    name: "Vesper",
    description: "An enigmatic spirit drawn from a forgotten fairytale.",
    image: "/portraits/red-horn.webp",
    kind: "concept",
  },
  {
    id: "concept-ren",
    name: "Ren",
    description: "A restless rival with a story yet to be written.",
    image: "/portraits/red-boy.webp",
    kind: "concept",
  },
];

function Icon({ name, size = 20 }: { name: "search" | "book" | "pen" | "compass" | "arrow" | "check" | "plus" | "close"; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    search: <><circle cx="11" cy="11" r="6.75" /><path d="m16 16 4 4" /></>,
    book: <><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1ZM12 5v15" /></>,
    pen: <><path d="m4 20 4.5-1 11-11a2.2 2.2 0 0 0-3.1-3.1l-11 11L4 20ZM14.5 6.5l3 3" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2.5 5-4.5 2 2.5-5 4.5-2Z" /></>,
    arrow: <><path d="M4 12h15m-6-6 6 6-6 6" /></>,
    check: <><path d="m5 12 4.5 4.5L19 7" /></>,
    plus: <><path d="M12 4v16M4 12h16" /></>,
    close: <><path d="M5 5l14 14M19 5 5 19" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Cover({ item, selected, onSelect }: { item: ShelfItem; selected: boolean; onSelect: () => void }) {
  const inner = (
    <>
      <span className={"em-cover em-cover-" + item.kind}>
        {item.image ? <img src={item.image} alt={"Portrait of " + item.name} loading="lazy" /> : <span className="em-cover-monogram">{item.name.slice(0, 1)}</span>}
        <span className="em-cover-edition">{item.kind === "sample" ? "STORY PREVIEW" : item.kind === "concept" ? "ART CONCEPT" : item.kind === "published" ? "PUBLISHED" : "YOUR CHARACTER"}</span>
        {selected && <span className="em-cover-selected"><Icon name="check" size={15} /></span>}
      </span>
      <span className="em-cover-title">{item.name}</span>
      <span className="em-cover-desc">{item.description}</span>
      <span className="em-cover-caption">{item.kind === "sample" ? "Sample · View rehearsal" : item.kind === "concept" ? "Artwork only · coming later" : item.kind === "published" ? `By ${item.creator || "a creator"} · View public profile` : selected ? "Selected for your cast" : "Tap to add to your cast"}</span>
    </>
  );
  if (item.kind === "sample") {
    return <Link className="em-book-card" href="/rehearsal" aria-label={"Open the rehearsal demo featuring sample character " + item.name}>{inner}</Link>;
  }
  if (item.kind === "concept") {
    return <div className="em-book-card em-book-concept" aria-label={"Artwork concept " + item.name + ", not yet playable"}>{inner}</div>;
  }
  if (item.kind === "published") {
    // Link by public Listing ID. Never pass a private Character ID into public
    // navigation or the legacy unpaid rehearsal Scene API.
    return <Link className="em-book-card" href={"/marketplace/" + encodeURIComponent(item.listingId!)} aria-label={"View published character " + item.name}>{inner}</Link>;
  }
  return <button type="button" className="em-book-card em-selectable" onClick={onSelect} aria-pressed={selected} aria-label={(selected ? "Remove " : "Select ") + item.name + (selected ? " from" : " for") + " your cast"}>{inner}</button>;
}

export function MarketplaceDiscover() {
  const router = useRouter();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [published, setPublished] = useState<MarketplaceListing[]>([]);
  const [ownedListings, setOwnedListings] = useState<OwnedListingDetail[]>([]);
  const [ownedLoading, setOwnedLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [publishedLoading, setPublishedLoading] = useState(true);
  const [publishedError, setPublishedError] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "published" | "mine" | "samples">("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    rehearsal<Character[]>("/characters")
      .then((records) => { if (active) setCharacters(records); })
      .catch(() => { if (active) setCharacters([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listPublishedListings(50, controller.signal)
      .then((records) => {
        if (!controller.signal.aborted) setPublished(records);
      })
      .catch(() => {
        if (!controller.signal.aborted) setPublishedError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPublishedLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listOwnedListings(controller.signal)
      .then((records) => { if (!controller.signal.aborted) setOwnedListings(records); })
      .catch(() => {
        // Anonymous discovery must remain available; don't expose owner data.
      })
      .finally(() => { if (!controller.signal.aborted) setOwnedLoading(false); });
    return () => controller.abort();
  }, []);

  const mine = useMemo<ShelfItem[]>(() => characters.map((c) => ({
    id: c.id,
    name: c.profile.name,
    description: c.profile.short_description || "An original character awaiting a story.",
    image: c.current_image_id ? "/api/characters/" + c.id + "/images/" + c.current_image_id + "/file" : null,
    kind: "mine",
  })), [characters]);

  const publishedShelf = useMemo<ShelfItem[]>(() => published.map((listing) => ({
    id: `published:${listing.listing_id}`,
    listingId: listing.listing_id,
    name: listing.name,
    description: listing.short_description,
    image: listing.cover_image_url,
    kind: "published",
    creator: listing.creator_display_name,
    tags: listing.tags,
  })), [published]);

  const visible = useMemo(() => {
    // An owned published character appears once in All, as its public listing.
    // My characters still shows the private source character for editing.
    const publishedCharacterIds = new Set(
      ownedListings.filter((item) => item.status === "published").map((item) => item.character_id),
    );
    const unpublishedMine = mine.filter((item) => !publishedCharacterIds.has(item.id));
    const collection = filter === "published" ? publishedShelf
      : filter === "mine" ? mine
      : filter === "samples" ? samples
      : ownedLoading ? samples
      : [...publishedShelf, ...unpublishedMine, ...samples];
    const term = query.trim().toLowerCase();
    return term ? collection.filter((item) =>
      [item.name, item.description, item.creator || "", ...(item.tags || [])]
        .join(" ").toLowerCase().includes(term),
    ) : collection;
  }, [publishedShelf, mine, ownedListings, ownedLoading, filter, query]);

  const collectionLoading = filter === "mine" ? loading
    : filter === "published" ? publishedLoading
    : filter === "samples" ? false
    : loading || publishedLoading || ownedLoading;

  function toggle(id: string) {
    setError("");
    setSelected((old) => old.includes(id) ? old.filter((x) => x !== id) : old.length < 2 ? [...old, id] : [old[1], id]);
  }

  async function createWithCast() {
    if (selected.length !== 2 || starting) return;
    setStarting(true);
    setError("");
    try {
      // Stage 2 is still the local rehearsal, not a paid marketplace checkout.
      const scene = await rehearsal<Scene>("/scenes", {
        operation_id: operation(),
        character_ids: selected,
        setup: { ...blankSetup, language: "en" },
      });
      router.push("/rehearsal?view=setup&scene=" + encodeURIComponent(scene.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open your story. Please try again.");
      setStarting(false);
    }
  }

  return (
    <main className="em-app">
      <div className="em-page">
        <header className="em-header">
          <Link className="em-brand" href="/marketplace" aria-label="Echoloom Discover home"><img className="em-brand-icon" src="/echoloom-gothic-mark.svg" alt="" aria-hidden="true" /><span>Echoloom<span className="em-brand-dot">.</span></span></Link>
          <Link href="/characters/new" className="em-top-create" aria-label="Create a new character"><Icon name="plus" size={19}/></Link>
        </header>

        <section className="em-hero" aria-labelledby="em-hero-heading">
          <div className="em-hero-ornament" aria-hidden="true">✳</div>
          <span className="em-kicker">DISCOVER <span>·</span> CHARACTERS</span>
          <h1 id="em-hero-heading">A new chapter<br/>begins with <em>you.</em></h1>
          <Link className="em-hero-link" href="/rehearsal">Open story studio <Icon name="arrow" size={16}/></Link>
        </section>

        <section className="em-discover" aria-labelledby="em-discover-heading">
          <div className="em-section-title">
            <div><h2 id="em-discover-heading">Discover characters</h2></div>
            <span className="em-section-star" aria-hidden="true">✷</span>
          </div>
          <label className="em-search">
            <Icon name="search" size={18}/>
            <span className="em-sr-only">Search characters</span>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search characters and stories" />
          </label>
          <div className="em-filters" role="group" aria-label="Character collection filter">
            {([["all","All characters"],["published","Published"],["mine","My characters"],["samples","Art previews"]] as const).map(([key,label]) => (
              <button key={key} type="button" onClick={() => setFilter(key)} aria-pressed={filter === key} className={filter === key ? "em-filter active" : "em-filter"}>{label}</button>
            ))}
          </div>
          <div className="em-shelf-header" role="status"><span>{collectionLoading ? "Loading…" : `${visible.length} characters`}</span></div>
          {visible.length ? (
            <div className="em-book-grid">
              {visible.map((item) => <Cover key={item.id} item={item} selected={selected.includes(item.id)} onSelect={() => toggle(item.id)}/>)}
            </div>
          ) : (
            <div className="em-empty">
              <span aria-hidden="true">✶</span><h3>{collectionLoading ? "Opening the library…" : query ? "No matching characters" : filter === "published" ? "No published characters yet" : "Your shelf is waiting"}</h3>
              {query && !collectionLoading && <p>Try another search.</p>}
              {!query && !collectionLoading && filter !== "published" && <Link href="/characters/new">Create a character <Icon name="arrow" size={15}/></Link>}
            </div>
          )}
          {publishedError && filter !== "mine" && filter !== "samples" && <p className="em-error" role="alert">Couldn’t load listings. Please refresh.</p>}
        </section>
      </div>

      {selected.length > 0 && <aside className="em-cast-tray" aria-label="Selected story cast">
        <div className="em-cast-copy"><span>YOUR STORY CAST <span className="em-cast-count">{selected.length}/2</span></span><p>{selected.map((id) => mine.find((x) => x.id === id)?.name).filter(Boolean).join(" & ") || "Choose your characters"}</p></div>
        {selected.length === 2 ? <button type="button" disabled={starting} onClick={() => void createWithCast()} className="em-cast-action">{starting ? "Opening…" : "Set the scene"} <Icon name="arrow" size={17}/></button> : <span className="em-cast-instruction">Choose one more</span>}
        <button type="button" onClick={() => setSelected([])} className="em-cast-clear" aria-label="Clear selected characters"><Icon name="close" size={15}/></button>
      </aside>}
      {error && <p className="em-error" role="alert">{error}</p>}

      <nav className="em-bottom-nav" aria-label="Primary navigation">
        <Link href="/marketplace" aria-current="page"><Icon name="compass" size={21}/><span>Discover</span></Link>
        <Link href="/rehearsal?view=characters"><Icon name="book" size={21}/><span>Characters</span></Link>
        <Link href="/rehearsal"><Icon name="pen" size={21}/><span>My stories</span></Link>
      </nav>
    </main>
  );
}

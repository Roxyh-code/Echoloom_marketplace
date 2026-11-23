"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Character, Scene, CreateSceneInput, CastSource } from "./rehearsal-api";
import { blankSetup, operation, rehearsal } from "./rehearsal-api";
import { getPublishedListing, listOwnedListings, listPublishedListings, type MarketplaceListing, type OwnedListingDetail } from "./marketplace-api";
import { addCast, listingChoice, privateChoice, readCast, saveCast, type CastChoice } from "./marketplace-casting";
import { placeholderCharacters } from "./marketplace-placeholders";
import { MobileBottomNav } from "./mobile-bottom-nav";

type ShelfItem = {
  id: string;
  name: string;
  description: string;
  image: string | null;
  kind: "placeholder" | "mine" | "published";
  listingId?: string;
  creator?: string;
  tags?: string[];
  revision?: number;
};


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
        {selected && <span className="em-cover-selected"><Icon name="check" size={15} /></span>}
      </span>
      <span className="em-cover-title">{item.name}</span>
      <span className="em-cover-desc">{item.description}</span>
    </>
  );
  if (item.kind === "placeholder") {
    // A static frontend preview is not a real public Listing or castable Character.
    return <Link className="em-book-card" href={"/marketplace/preview/" + encodeURIComponent(item.id)} aria-label={"View character " + item.name}>{inner}</Link>;
  }
  if (item.kind === "published") {
    // Public card navigation and selection are separate accessible controls.
    // Do not pass private Character IDs through public navigation.
    return (
      <div className="em-book-entry">
        <Link className="em-book-card" href={"/marketplace/" + encodeURIComponent(item.listingId!)} aria-label={"View published character " + item.name}>{inner}</Link>
        <button type="button" className="em-card-select" onClick={onSelect} aria-pressed={selected}
          aria-label={(selected ? "Remove " : "Select ") + item.name + (selected ? " from" : " for") + " your cast"}>
          <Icon name={selected ? "check" : "plus"} size={15} />
          {selected ? "In your cast" : "Add to cast"}
        </button>
      </div>
    );
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
  const [filter, setFilter] = useState<"all" | "published" | "mine">("all");
  const [selected, setSelected] = useState<CastChoice[]>([]);
  const [replaceSlot, setReplaceSlot] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setSelected(readCast());
  }, []);

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
    revision: listing.revision,
    name: listing.name,
    description: listing.short_description,
    image: listing.cover_image_url,
    kind: "published",
    creator: listing.creator_display_name,
    tags: listing.tags,
  })), [published]);

  const visible = useMemo(() => {
    // Own published characters appear once in All; My characters still shows
    // their private source for editing. The only public listings are API records.
    const publishedCharacterIds = new Set(
      ownedListings.filter((item) => item.status === "published").map((item) => item.character_id),
    );
    const unpublishedMine = mine.filter((item) => !publishedCharacterIds.has(item.id));
    // Temporary cards stand in for a sparse public catalog and phase out as
    // real creators publish. They are never inserted into the Published filter.
    const fallbackCount = Math.max(0, 4 - publishedShelf.length);
    const placeholders: ShelfItem[] = placeholderCharacters.slice(0, fallbackCount).map((item) => ({
      ...item,
      kind: "placeholder",
    }));
    const collection = filter === "published" ? publishedShelf
      : filter === "mine" ? mine
      : ownedLoading || publishedLoading ? []
      : [...publishedShelf, ...unpublishedMine, ...placeholders];
    const term = query.trim().toLowerCase();
    return term ? collection.filter((item) =>
      [item.name, item.description, item.creator || "", ...(item.tags || [])]
        .join(" ").toLowerCase().includes(term),
    ) : collection;
  }, [publishedShelf, mine, ownedListings, ownedLoading, publishedLoading, filter, query]);

  const collectionLoading = filter === "mine" ? loading
    : filter === "published" ? publishedLoading
    : loading || publishedLoading || ownedLoading;

  function choose(item: ShelfItem) {
    if (item.kind === "placeholder") return;
    setError("");
    const choice = item.kind === "published"
      ? listingChoice({
          listing_id: item.listingId!,
          revision: item.revision!,
          name: item.name,
          short_description: item.description,
          cover_image_url: item.image,
          tags: item.tags || [],
          public_personality: [],
          creator_display_name: item.creator || "",
        })
      : privateChoice(item.id, item.name, item.image);
    const previous = selected;
    if (previous.some((v) => v.key === choice.key)) {
      updateCast(previous.filter((v) => v.key !== choice.key));
      return;
    }
    // If the current account owns the listing, the same underlying
    // Character cannot fill both a public and a private seat.
    const underlying = (candidate: CastChoice) => {
      if (candidate.source.source === "private") return candidate.source.character_id;
      return ownedListings.find((v) => v.listing_id === candidate.source.listing_id)?.character_id || candidate.key;
    };
    if (previous.some((v) => underlying(v) === underlying(choice))) {
      setError("That character is already in your cast. Choose someone different.");
      return;
    }
    updateCast(addCast(previous, choice, replaceSlot));
    setReplaceSlot(null);
  }

  function updateCast(next: CastChoice[]) {
    setSelected(next);
    saveCast(next);
  }

  async function createWithCast() {
    if (selected.length !== 2 || starting) return;
    setStarting(true);
    setError("");
    try {
      // Public and mixed casting use server-verified Listing sources; two
      // private characters continue using the backward-compatible legacy API.
      await Promise.all(selected.map(async (entry) => {
        if (entry.source.source !== "listing") return;
        const current = await getPublishedListing(entry.source.listing_id);
        if (current.revision !== entry.source.expected_revision)
          throw new Error(current.name + " was updated. Remove and select the new version.");
      }));
      const request: CreateSceneInput = {
        operation_id: operation(),
        setup: { ...blankSetup, language: "en" },
      };
      if (selected.every((entry) => entry.source.source === "private")) {
        // Preserve existing local/private draft behavior, including the
        // unclaimed-account bootstrap path used by legacy Rehearsal.
        request.character_ids = selected.map((entry) =>
          (entry.source as Extract<CastSource, { source: "private" }>).character_id
        );
      } else {
        // All public and mixed-source scenes use backend-verified Listing IDs.
        request.cast_sources = selected.map((entry) => entry.source) as [CastSource, CastSource];
      }
      const scene = await rehearsal<Scene>("/scenes", request);
      updateCast([]);
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
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search characters" />
          </label>
          <div className="em-filters" role="group" aria-label="Character collection filter">
            {([["all","All characters"],["published","Published"],["mine","My characters"]] as const).map(([key,label]) => (
              <button key={key} type="button" onClick={() => setFilter(key)} aria-pressed={filter === key} className={filter === key ? "em-filter active" : "em-filter"}>{label}</button>
            ))}
          </div>
          <div className="em-shelf-header" role="status"><span>{collectionLoading ? "Loading…" : `${visible.length} characters`}</span></div>
          {visible.length ? (
            <div className="em-book-grid">
              {visible.map((item) => <Cover key={item.id} item={item} selected={selected.some((v) => v.key === (item.kind === "published" ? "listing:" + item.listingId : "private:" + item.id))} onSelect={() => choose(item)}/>)}
            </div>
          ) : (
            <div className="em-empty">
              <span aria-hidden="true">✶</span><h3>{collectionLoading ? "Opening the library…" : query ? "No matching characters" : filter === "published" ? "No published characters yet" : "Your shelf is waiting"}</h3>
              {query && !collectionLoading && <p>Try another search.</p>}
              {!query && !collectionLoading && filter !== "published" && <Link href="/characters/new">Create a character <Icon name="arrow" size={15}/></Link>}
            </div>
          )}
          {publishedError && filter !== "mine" && <p className="em-error" role="alert">Couldn’t load listings. Please refresh.</p>}
        </section>
      </div>

      {selected.length > 0 && <aside className="em-cast-tray" aria-label="Selected story cast">
        <div className="em-cast-copy">
          <span>YOUR STORY CAST <span className="em-cast-count">{selected.length}/2</span></span>
          <div className="em-cast-members">
            {selected.map((entry, index) => (
              <div key={entry.key} className="em-cast-member">
                <span className="em-cast-member-name">{index === 0 ? "A" : "B"} · {entry.name}</span>
                <button type="button" className={replaceSlot === index ? "em-cast-replace active" : "em-cast-replace"}
                  aria-label={"Replace " + entry.name} aria-pressed={replaceSlot === index}
                  onClick={() => setReplaceSlot(replaceSlot === index ? null : index)}>Replace</button>
                <button type="button" className="em-cast-remove" aria-label={"Remove " + entry.name + " from cast"}
                  onClick={() => { updateCast(selected.filter((v) => v.key !== entry.key)); setReplaceSlot(null); }}>×</button>
              </div>
            ))}
          </div>
          {replaceSlot !== null && <small className="em-cast-hint">Choose a character above to replace slot {replaceSlot ? "B" : "A"}.</small>}
        </div>
        <div className="em-cast-controls">
          {selected.length === 2 ? <button type="button" disabled={starting} onClick={() => void createWithCast()} className="em-cast-action">{starting ? "Opening…" : "Set the scene"} <Icon name="arrow" size={17}/></button> : <span className="em-cast-instruction">Choose one more</span>}
          <button type="button" onClick={() => { updateCast([]); setReplaceSlot(null); }} className="em-cast-clear" aria-label="Clear selected characters"><Icon name="close" size={15}/></button>
        </div>
      </aside>}
      {error && <p className="em-error" role="alert">{error}</p>}

      <MobileBottomNav active="discover" />
    </main>
  );
}

"use client";
import { useEffect, useRef, useState } from "react";
import {
  api,
  Character,
  Health,
  Portrait,
  Profile,
  Proposal,
  Revision,
} from "./api";
import { creator } from "./creator-api";
import { CharacterVoice } from "./character-voice";
import { ResearchSources } from "./research-sources";
import researchStyles from "./character-research.module.css";
import { listOwnedListings, type OwnedListingDetail } from "./marketplace-api";
import { localGet, localPut, operation } from "./rehearsal-api";
type Mode = "library" | "create" | "detail";
type Person = Character & { archived?: boolean };
type Creation = { request_id: string; description: string; character_id?: string; research?: boolean };
function Picture({
  character,
  large = false,
}: {
  character: Character;
  large?: boolean;
}) {
  const [bad, setBad] = useState(false);
  const image = character.current_image_id;
  useEffect(() => setBad(false), [image]);
  return (
    <div className={large ? "mc-portrait" : "rh-avatar"}>
      {image && !bad ? (
        <img
          src={`/api/characters/${character.id}/images/${image}/file`}
          alt={"Portrait of " + character.profile.name}
          onError={() => setBad(true)}
        />
      ) : (
        <span>{character.profile.name.slice(0, 1)}</span>
      )}
    </div>
  );
}
function Panel({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const trigger = document.activeElement as HTMLElement;
    ref.current?.showModal();
    return () => {
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="rh-sheet mc-sheet"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="rh-grab" />
      <header>
        <h2>{title}</h2>
        <button className="rh-icon" aria-label="Close panel" onClick={close}>
          ×
        </button>
      </header>
      <div className="rh-sheet-body">{children}</div>
    </dialog>
  );
}
export function MobileCharacterStudio({
  initialCreate = false,
  picking = false,
  onExit,
  onPick,
  onStart,
  onChanged,
  onMode,
}: {
  initialCreate?: boolean;
  picking?: boolean;
  onExit: () => void;
  onPick: (c: Character) => Promise<void>;
  onStart: (c: Character) => Promise<void>;
  onChanged: () => Promise<void>;
  onMode: (mode: Mode) => void;
}) {
  const [mode, setMode] = useState<Mode>(initialCreate ? "create" : "library");
  const [list, setList] = useState<Person[]>([]);
  const [person, setPerson] = useState<Person | null>(null);
  const [ownedListings, setOwnedListings] = useState<OwnedListingDetail[]>([]);
  const [ownedLoading, setOwnedLoading] = useState(true);
  const [ownedError, setOwnedError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const [description, setDescription] = useState("");
  const [research,setResearch]=useState(true);
  const [researchPhase,setResearchPhase]=useState("");
  const [pending, setPending] = useState<Creation | null>(null);
  const [imageError, setImageError] = useState("");
  const [reviewPortrait,setReviewPortrait]=useState(false);
  const [serverPortraitPending,setServerPortraitPending]=useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const voiceEnabled = useRef(false);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [panel, setPanel] = useState<
    "profile" | "refine" | "portrait" | "history" | "more" | null
  >(null);
  const [portraits, setPortraits] = useState<Portrait[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const guard = useRef(false);
  const creationGuard = useRef(false);
  const creationEpoch = useRef(0);
  const alive = useRef(true);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const personRef = useRef(person);
  personRef.current = person;
  const epoch = useRef(0);
  function url(next: Mode, cid?: string, replace = false) {
    const q = new URLSearchParams(location.search);
    q.set("view", "characters");
    q.delete("create");
    q.delete("character");
    if (next === "create") q.set("create", "1");
    if ((next === "detail" || next === "create") && cid) q.set("character", cid);
    setReviewId(next === "create" && cid ? cid : null);
    history[replace ? "replaceState" : "pushState"](
      null,
      "",
      "/rehearsal?" + q,
    );
    setMode(next);
    setPanel(null);
    setError("");
    onMode(next);
  }
  async function refresh(showArchived = archived) {
    const cs = await creator<Person[]>("/characters?archived=" + showArchived);
    if (alive.current) setList(cs);
    return cs;
  }
  async function open(cid: string, replace = false, next: Mode = "detail") {
    const n = ++epoch.current;
    setLoading(true);
    try {
      const c = await api<Person>("/characters/" + cid);
      if (alive.current && n === epoch.current) {
        setPerson(c);
        setImageError("");
        url(next, c.id, replace);
      }
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setLoading(false);
    }
  }
  useEffect(() => {
    let active = true;
    listOwnedListings()
      .then((records) => { if (active) setOwnedListings(records); })
      .catch(() => { if (active) setOwnedError("Listing status unavailable. Refresh before publishing."); })
      .finally(() => { if (active) setOwnedLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    alive.current = true;
    const q = new URLSearchParams(location.search);
    const job = localGet<Creation | null>("character-creation", null);
    // Opening "Create" from another screen mounts a FRESH Studio instance,
    // so startCreate() is not called. Discard a completed Profile's lingering
    // portrait-only job from the new form; its image still completes server-side.
    // Retain an unfinished Profile (no character_id) for explicit recovery.
    const newCharacter = initialCreate || q.has("create");
    if (newCharacter && !q.get("character") && job?.character_id) {
      creationEpoch.current++;
      setDescription("");
      localPut("character-description", "");
      setPending(null);
      localPut("character-creation", null);
    } else {
      setDescription(localGet("character-description", ""));
      setPending(job);
    }
    api<Health>("/health")
      .then(h => { voiceEnabled.current = !!h.voice_enabled; setHealth(h); })
      .catch(() => {});
    void refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    if (q.get("character")) void open(q.get("character")!, true, q.has("create") ? "create" : "detail");
    else if (initialCreate || q.has("create")) {
      setMode("create");
      onMode("create");
    } else onMode("library");
    const pop = () => {
      const q = new URLSearchParams(location.search);
      if (q.get("view") !== "characters") return;
      if (q.get("character")) void open(q.get("character")!, true, q.has("create") ? "create" : "detail");
      else {
        const next = q.has("create") ? "create" : "library";
        setMode(next);
        setReviewId(null);
        if (next === "create") setPerson(null);
        setPanel(null);
        onMode(next);
      }
    };
    window.addEventListener("popstate", pop);
    return () => {
      alive.current = false;
      epoch.current++;
      window.removeEventListener("popstate", pop);
    };
  }, []);
  async function run(fn: () => Promise<void>) {
    if (guard.current) return;
    guard.current = true;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      guard.current = false;
      if (alive.current) setBusy(false);
    }
  }
  async function changed() {
    if (!alive.current) return;
    await refresh();
    await onChanged();
  }
  async function reloadPerson() {
    const c = await api<Person>("/characters/" + personRef.current!.id);
    if (alive.current) setPerson(c);
    return c;
  }
  function startCreate() {
    // Invalidate any prior asynchronous job poll before a new creation.
    creationEpoch.current++;
    // Create New must always start with an EMPTY form. A previous request
    // may still be pending for Profile/portrait recovery; this explicit user
    // action detaches the local form from that job but never cancels the
    // server worker. "Resume character creation" remains a separate action.
    if (pending) {
      setPending(null);
      localPut("character-creation", null);
    }
    setDescription("");
    setResearch(true);
    setResearchPhase("");
    localPut("character-description", "");
    setPerson(null);
    setImageError("");
    url("create");
  }
  async function createCharacter(retry?: Creation) {
    if (creationGuard.current) return;
    creationGuard.current = true;
    setCreating(true);
    setError("");
    setImageError("");
    const job = retry || {
      request_id: operation(),
      description: description.trim(),
      ...(health?.research_enabled && research ? {research:true}:{}),
    };
    setPending(job);
    setResearchPhase(job.research?"identifying":"");
    localPut("character-creation", job);
    try {
      const r = await creator<{
        character_id: string;
        phase: string;
        image_error?: string;
      }>("/characters", job);
      if (!alive.current) return;
      const c = await api<Person>("/characters/" + r.character_id);
      if (!alive.current) return;
      if (modeRef.current === "create" || personRef.current?.id === c.id) {
        setPerson(c);
        setImageError(r.image_error || "");
      }
      const portraitPending = r.phase === "portrait_pending";
      const tracked = { ...job, character_id: c.id };
      setPending(portraitPending ? tracked : null);
      localPut("character-creation", portraitPending ? tracked : null);
      localPut("character-description", "");
      setDescription("");
      // The new Profile should be interactive IMMEDIATELY. Do not await
      // library/Scene refresh before navigating: those unrelated network
      // calls can be slower or fail while the Character itself is saved.
      if (modeRef.current === "create") url(voiceEnabled.current ? "create" : "detail", c.id, voiceEnabled.current);
      else setNotice(c.profile.name + " is saved in your characters.");
      void changed().catch(() => {
        if (alive.current)
          setNotice("Character saved. Refresh to update the library.");
      });
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      creationGuard.current = false;
      if (alive.current) setCreating(false);
    }
  }
  // Recover a profile/portrait even after refresh or a dropped POST response. Never regenerate the profile.
  useEffect(() => {
    if (!pending) return;
    const token = creationEpoch.current;
    let active = true;
    let polling = false;
    const tick = async () => {
      if (polling) return;
      polling = true;
      try {
        const j = await creator<{
          status: string;
          result?: {
            character_id?: string;
            image_error?: string;
            detail?: string;
            phase?: string;
          };
        }>("/jobs/" + pending.request_id);
        if (!active || token !== creationEpoch.current) return;
        if (pending.research && j.result?.phase) setResearchPhase(j.result.phase);
        if (j.result?.character_id) {
          const c = await api<Person>("/characters/" + j.result.character_id);
          if (!active || token !== creationEpoch.current) return;
          if (modeRef.current === "create" || personRef.current?.id === c.id)
            setPerson(c);
          if (j.status === "pending") {
            const tracked = { ...pending, character_id: c.id };
            setPending((previous) => previous?.request_id === tracked.request_id
              ? tracked : previous);
            localPut("character-creation", tracked);
            if (modeRef.current === "create") url(voiceEnabled.current ? "create" : "detail", c.id, true);
          }
          if (j.status === "succeeded") {
            setImageError(j.result.image_error || "");
            setPending(null);
            setCreating(false);
            localPut("character-creation", null);
            localPut("character-description", "");
            setDescription("");
            if (alive.current && modeRef.current === "create")
              url(voiceEnabled.current ? "create" : "detail", c.id, true);
            void changed().catch(() => {
              if (alive.current)
                setNotice("Character saved. Refresh to update the library.");
            });
          }
        } else if (j.status === "failed") {
          setError(
            j.result?.detail ||
              "Character creation did not complete. Retry your saved description.",
          );
          setCreating(false);
        }
      } catch {
        /* The saved request ID remains available for explicit retry. */
      } finally {
        polling = false;
      }
    };
    void tick();
    const timer = setInterval(tick, 1500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [pending?.request_id]);
  async function loadPortraits() {
    const ps = await api<Portrait[]>(
      "/characters/" + personRef.current!.id + "/images",
    );
    if (alive.current) setPortraits(ps);
  }
  useEffect(()=>{
    setServerPortraitPending(false);
    if(!person || person.current_image_id || person.archived || mode==="library")return;
    const cid=person.id;
    let active=true;
    let timer:ReturnType<typeof setTimeout>|undefined;
    async function check(){
      try {
        const status=await creator<{state:string;error?:string|null}>("/characters/"+cid+"/portrait/status");
        if(!active)return;
        setServerPortraitPending(status.state==="pending");
        if(status.state==="pending")timer=setTimeout(check,2000);
        else if(status.state==="ready") {
          const fresh=await api<Person>("/characters/"+cid);
          if(active&&personRef.current?.id===cid)setPerson(fresh);
        } else if(status.error)setImageError(status.error);
      } catch {}
    }
    void check();
    return ()=>{active=false;if(timer)clearTimeout(timer);};
  },[person?.id,person?.current_image_id,mode]);
  async function makePortrait(edit: boolean, instruction = "") {
    const c = personRef.current!;
    const payload = {
      editing: edit,
      instruction,
      expected_image_id: c.current_image_id,
    };
    const key = "portrait-operation:" + c.id;
    const prior = localGet<{
      payload: typeof payload;
      request_id: string;
    } | null>(key, null);
    const request_id =
      prior && JSON.stringify(prior.payload) === JSON.stringify(payload)
        ? prior.request_id
        : operation();
    localPut(key, { payload, request_id });
    try {
      await creator("/characters/" + c.id + "/portrait", {
        request_id,
        ...payload,
      });
      if (!alive.current || personRef.current?.id !== c.id) return;
      localPut(key, null);
      await loadPortraits();
      const fresh = await reloadPerson();
      if (!fresh.current_image_id) {
        const ps = await api<Portrait[]>("/characters/" + c.id + "/images");
        if (ps.length) {
          await api(`/characters/${c.id}/images/${ps[0].id}/select`, {});
          await reloadPerson();
        }
      }
      setImageError("");
      setNotice("Portrait ready. Choose the version you prefer.");
      await changed();
    } catch (e) {
      await loadPortraits().catch(() => {});
      const message=e instanceof Error?e.message:"Portrait generation failed.";
      if(alive.current && personRef.current?.id===c.id){
        setImageError(message);
        if(/content moderation|moderation_blocked|content_policy_violation|safety_violations/i.test(message))setPanel(null);
      }
      throw e;
    }
  }
  useEffect(() => {
    if (panel === "portrait" && person)
      void loadPortraits().catch((e) => setError(e.message));
    if (panel === "history" && person)
      void api<Revision[]>("/characters/" + person.id + "/versions")
        .then(setRevisions)
        .catch((e) => setError(e.message));
  }, [panel, person?.id]);
  function back() {
    setError("");
    if (mode === "library") onExit();
    else {
      epoch.current++;
      url("library");
      void refresh().catch((e) => setError(e.message));
    }
  }
  const reviewing = mode === "create" && !!person && reviewId === person.id;
  const buttonDisabled = busy || creating;
  const portraitGenerating = serverPortraitPending || !!(pending?.character_id && person?.id === pending.character_id &&
    !person.current_image_id);
  const moderationBlocked=/content moderation|moderation_blocked|content_policy_violation|safety_violations/i.test(imageError);
  const field = (f: FormData, k: string) => String(f.get(k) || "").trim();
  return (
    <>
      <header className="rh-top mc-top">
        <button className="rh-icon" aria-label="Back" onClick={back}>
          ‹
        </button>
        <div>
          <span className="rh-top-title">
            {mode === "library"
              ? "Your characters"
              : mode === "create"
                ? "Create a character"
                : person?.profile.name || "Character"}
          </span>
          <small>
            {mode === "create"
              ? "A PERSONALITY. A PORTRAIT. A VOICE."
              : picking
                ? "CHOOSE YOUR CAST"
                : "THE CHARACTER LIBRARY"}
          </small>
        </div>
        <button
          className="rh-icon"
          aria-label={
            person && mode === "detail" ? "Character options" : "New character"
          }
          disabled={buttonDisabled}
          onClick={() =>
            person && mode === "detail" ? setPanel("more") : startCreate()
          }
        >
          {person && mode === "detail" ? "···" : "＋"}
        </button>
      </header>
      {!panel && (error || notice) && (
        <div
          className={"rh-alert " + (error ? "error" : "")}
          role={error ? "alert" : "status"}
        >
          <span>{error || notice}</span>
          <div>
            <button
              aria-label="Dismiss message"
              onClick={() => {
                setError("");
                setNotice("");
              }}
            >
              ×
            </button>
          </div>
        </div>
      )}
      {mode === "library" && (
        <div className="rh-scroll rh-pad mc-library">
          <span className="rh-eyebrow">THE CHARACTER LIBRARY · VOL. 01</span>
          <h1>
            Every story
            <br />
            <em>starts with someone.</em>
          </h1>
          <button
            className="rh-primary"
            aria-label="Create character"
            onClick={startCreate}
            disabled={buttonDisabled}
          >
            ＋ Create character <span>→</span>
          </button>
          {!picking && !archived && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, margin: "12px 0 18px" }}>
              <button type="button" className="rh-secondary" style={{ minHeight: 64, width: "100%", padding: "10px 8px", whiteSpace: "normal", textAlign: "center" }}
                aria-label={ownedListings.length ? "Publish or manage listings" : "Publish a character"}
                onClick={() => window.location.assign("/characters/publish")}>
                {ownedListings.length ? "My listings" : "Publish character"} →
              </button>
              <button type="button" className="rh-secondary" aria-label="Creator earnings" style={{ minHeight: 64, width: "100%", padding: "10px 8px", whiteSpace: "normal", textAlign: "center" }}
                onClick={() => window.location.assign("/characters/earnings")}>
                Creator earnings →
              </button>
            </div>
          )}
          {pending && (
            <button
              className="mc-pending"
              onClick={() => {
                setDescription(pending.description);
                url("create");
              }}
            >
              <span>✧</span>
              <span>
                <strong>Resume character creation</strong>
                <small>Your description and request are saved.</small>
              </span>
              <span>→</span>
            </button>
          )}
          <label className="rh-search">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              aria-hidden="true"
            >
              <circle cx="10" cy="10" r="7" />
              <path d="M15 15l6 6" />
            </svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Find a character…"
              aria-label="Search characters"
            />
          </label>
          <div className="rh-filters">
            <button
              className={!archived ? "active" : ""}
              onClick={() => {
                setArchived(false);
                void refresh(false).catch((e) => setError(e.message));
              }}
            >
              My characters
            </button>
            <button
              className={archived ? "active" : ""}
              onClick={() => {
                setArchived(true);
                void refresh(true).catch((e) => setError(e.message));
              }}
            >
              Archived
            </button>
          </div>
          {loading ? (
            <p className="rh-muted">Opening your cast…</p>
          ) : (
            <div className="mc-character-grid">
              {list
                .filter((c) =>
                  (c.profile.name + " " + c.original_description)
                    .toLowerCase()
                    .includes(search.toLowerCase()),
                )
                .map((c) => (
                  <button
                    className="mc-character-card"
                    key={c.id}
                    onClick={() => open(c.id)}
                  >
                    <Picture character={c} large />
                    <span className="mc-character-caption">
                      <strong>{c.profile.name}</strong>
                      <small>
                        {c.profile.short_description || c.original_description}
                      </small>
                      <span>
                        {picking
                          ? "Choose for this scene"
                          : "Meet this character"}{" "}
                        →
                      </span>
                    </span>
                  </button>
                ))}
            </div>
          )}
          {!loading && !list.length && (
            <div className="rh-empty">
              <span className="mc-empty-star">✧</span>
              <p>
                {archived
                  ? "Your archived characters will appear here."
                  : "Someone only you could imagine."}
              </p>
            </div>
          )}
        </div>
      )}
      {mode === "create" && !reviewing && (
        <>
          <div className="rh-scroll rh-pad mc-create">
            <span className="rh-eyebrow">YOUR CHARACTER · A NEW STORY</span>
            <h1>
              Who do you
              <br />
              <em>have in mind?</em>
            </h1>
            <form
              id="mc-create"
              onSubmit={(e) => {
                e.preventDefault();
                // The browser's submitted field is authoritative even if
                // React has not committed its last controlled onChange yet.
                // This matters for quick submits on narrow/mobile screens.
                const submitted = String(
                  new FormData(e.currentTarget).get("description") || "",
                ).trim();
                void createCharacter(pending || {
                  request_id: operation(),
                  description: submitted,
                  ...(health?.research_enabled && research ? {research:true}:{}),
                });
              }}
            >
              <label>
                Describe your character
                <textarea
                  name="description"
                  value={pending ? pending.description : description}
                  onChange={(e) => {
                    setDescription(e.target.value);
                    localPut("character-description", e.target.value);
                  }}
                  rows={8}
                  required
                  maxLength={health?.max_profile_input_chars || 5000}
                  disabled={!!pending || creating}
                  placeholder="A reserved astronomer with silver hair and a quiet, dry wit. She wants to save her observatory, but hides how much she fears failing…"
                />
              </label>
              {health?.research_enabled && <div className={researchStyles.toggle}>
                <button type="button" role="switch" aria-label="Research character" aria-checked={pending ? !!pending.research : research} disabled={!!pending||creating} onClick={()=>setResearch(v=>!v)}><span/></button>
                <label onClick={()=>{if(!pending&&!creating)setResearch(v=>!v);}}>Research character</label>
              </div>}
              {!pending && (
                <button
                  className="rh-text-button"
                  type="button"
                  onClick={() => {
                    const value =
                      "A reserved astronomer with silver hair and a quiet, dry wit. She wants to save her observatory, but hides how much she fears failing. Her voice is gentle and precise.";
                    setDescription(value);
                    localPut("character-description", value);
                  }}
                >
                  Try an example description →
                </button>
              )}
              {(creating || pending) && pending?.research && (
                <div className={researchStyles.progress} role="status"><span className={researchStyles.dot}/>{researchPhase==="researching"?"Researching character · Firecrawl":researchPhase==="building_profile"?"Creating character…":"Identifying character…"}</div>
              )}
              {(creating || pending) && !pending?.research && (
                <div className="mc-creation-progress" role="status">
                  <div className={person ? "done" : ""}>
                    <span>{person ? "✓" : "01"}</span>
                    <p>
                      <strong>
                        {person ? "Character saved" : "Creating the character"}
                      </strong>
                      <small>
                        {person?.profile.name ||
                          "Personality, appearance and voice"}
                      </small>
                    </p>
                  </div>
                  <div className={person?.current_image_id ? "done" : ""}>
                    <span>{person?.current_image_id ? "✓" : "02"}</span>
                    <p>
                      <strong>
                        {person?.current_image_id
                          ? "Portrait ready"
                          : person
                            ? "Creating the portrait"
                            : "Preparing visual profile"}
                      </strong>
                      <small>
                        {person
                          ? "Your character is safe while the portrait is generated."
                          : "Portrait starts after the profile is saved."}
                      </small>
                    </p>
                  </div>
                </div>
              )}
              {pending && !creating && (
                <p className="rh-muted">
                  {error
                    ? "Your description is saved. Retry the same creation."
                    : "Checking the saved request. Resume if the connection was interrupted."}
                </p>
              )}
            </form>
          </div>
          <footer className="rh-form-footer">
            <button
              className="rh-primary"
              form="mc-create"
              disabled={
                creating ||
                busy ||
                !(pending?.description || description).trim()
              }
            >
              {creating
                ? "Creating character & portrait…"
                : pending
                  ? "Resume creation"
                  : "Create character"}
              <span>✧</span>
            </button>
            {pending && !creating && (
              <button
                className="rh-text-button mc-center"
                onClick={() => {
                  setDescription(pending.description);
                  setPending(null);
                  localPut("character-creation", null);
                }}
              >
                Keep description & start a new request
              </button>
            )}
          </footer>
        </>
      )}
      {(mode === "detail" || reviewing) && person && (
        <>
          <div className="rh-scroll mc-detail">
            <div className="mc-character-cover">
              <Picture character={person} large />
              <div className="mc-cover-shade" />
              <div className="mc-cover-title">
                <span className="rh-eyebrow">
                  {reviewing ? "YOUR CHARACTER · CREATION PREVIEW" : "YOUR CHARACTER · VERSION " + person.profile_version}
                </span>
                <h1>{person.profile.name}</h1>
                <p>{person.profile.short_description}</p>
              </div>
              <button
                className="mc-cover-edit"
                onClick={() => {if(moderationBlocked&&!person.current_image_id){setReviewPortrait(true);setPanel("profile");}else setPanel("portrait");}}
              >
                {moderationBlocked&&!person.current_image_id?"Review portrait →":"Edit portrait →"}
              </button>
            </div>
            {portraitGenerating && (
              <div className="mc-portrait-pending" role="status">
                <span className="mc-portrait-spinner" aria-hidden="true">✧</span>
                <div>
                  <strong>Portrait generating in the background</strong>
                  <p>Your character is saved and ready to use. You can explore the
                    profile or choose a voice while the portrait finishes.</p>
                </div>
              </div>
            )}
            {imageError && !person.current_image_id && !portraitGenerating && (
              <div className="rh-alert error" role="alert">
                <span>{imageError}</span>
                <p>{moderationBlocked?"Your character is saved. Review the portrait requirements against platform rules.":"Your character is saved. Retry only the portrait."}</p>
                <button
                  disabled={busy}
                  onClick={() => {
                    if(moderationBlocked){setReviewPortrait(true);setPanel("profile");return;}
                    void run(async () => {setPanel("portrait");await makePortrait(false);});
                  }}
                >
                  {moderationBlocked?"Review portrait description":"Retry portrait"}
                </button>
              </div>
            )}
            <div className="rh-pad mc-profile-body">
              <ResearchSources character={person} />
              {reviewing && <p className="rh-muted">Profile saved. Choose a voice.</p>}
              {!person.archived && (!picking || reviewing) && <CharacterVoice key={person.id} id={person.id} profileVersion={person.profile_version} />}
              <div className="mc-edit-actions">
                <button
                  className="rh-secondary"
                  onClick={() => {setReviewPortrait(false);setPanel("profile");}}
                >
                  Edit character
                </button>
                <button
                  className="rh-secondary"
                  onClick={() => {
                    setProposal(null);
                    setPanel("refine");
                  }}
                >
                  Refine with AI
                </button>
              </div>
              <div className="mc-facts">
                {[
                  ["WANTS", person.profile.wants],
                  ["VOICE", person.profile.speech_style?.tone],
                  [
                    "CORE TRAITS",
                    person.profile.personality?.core_traits?.join(" · "),
                  ],
                ]
                  .filter(([, v]) => !!v)
                  .map(([k, v]) => (
                    <section key={k}>
                      <span className="rh-eyebrow">{k}</span>
                      <p>{v}</p>
                    </section>
                  ))}
              </div>

              <details className="rh-details">
                <summary>
                  Background & private details <span>＋</span>
                </summary>
                {[
                  ["Background", person.profile.backstory],
                  ["Why it matters", person.profile.why_it_matters],
                  ["Fear or boundary", person.profile.fear],
                  ["Private information", person.profile.private_information],
                  ["Original description", person.original_description],
                ]
                  .filter(([, v]) => !!v)
                  .map(([k, v]) => (
                    <section className="mc-fact" key={k}>
                      <h3>{k}</h3>
                      <p>{v}</p>
                    </section>
                  ))}
              </details>
              <button
                className="rh-text-button"
                onClick={() => setPanel("history")}
              >
                Character version history →
              </button>
            </div>
          </div>
          <footer className="rh-form-footer">
            <button
              className="rh-primary"
              disabled={buttonDisabled}
              onClick={() =>
                run(async () => {
                  if (reviewing) { url("detail", person.id, true); return; }
                  let c = person;
                  if (person.archived) {
                    await creator(
                      "/characters/" + person.id + "/archive",
                      { archived: false },
                      "PATCH",
                    );
                    c = await reloadPerson();
                    await changed();
                  }
                  if (picking) await onPick(c);
                  else await onStart(c);
                })
              }
            >
              {reviewing ? "Finish character creation" : person.archived
                ? "Unarchive & rehearse"
                : picking
                  ? "Use in this scene"
                  : "Rehearse with " + person.profile.name}
              <span>→</span>
            </button>
            {!reviewing && !picking && !person.archived && (
              <button
                type="button"
                className="rh-secondary"
                style={{ marginTop: 10 }}
                disabled={ownedLoading || !!ownedError}
                onClick={() =>
                  window.location.assign(
                    "/characters/publish?character=" + encodeURIComponent(person.id),
                  )
                }
              >
                {ownedLoading ? "Checking listing…" :
                  ownedListings.find((item) => item.character_id === person.id)?.status === "published"
                    ? "Manage Listing →"
                    : ownedListings.find((item) => item.character_id === person.id)?.status === "unpublished"
                      ? "Republish Listing →"
                      : "Publish to Marketplace →"}
              </button>
            )}
            {ownedError && !reviewing && !picking && !person.archived && (
              <p className="rh-muted" role="alert">{ownedError}</p>
            )}
          </footer>
        </>
      )}
      {panel && person && (
        <Panel
          title={
            {
              profile: "Shape your character",
              refine: "A little more like you imagined",
              portrait: "Their portrait",
              history: "Character versions",
              more: "Character options",
            }[panel]
          }
          close={() => {
            setPanel(null);
            setError("");
          }}
        >
          {error && (
            <div className="rh-alert error" role="alert">
              {error}
            </div>
          )}
          {panel === "profile" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                void run(async () => {
                  const p: Profile = {
                    ...person.profile,
                    name: field(f, "name"),
                    short_description: field(f, "short"),
                    wants: field(f, "wants"),
                    why_it_matters: field(f, "why"),
                    fear: field(f, "fear"),
                    private_information: field(f, "secret"),
                    backstory: field(f, "background"),
                    visual_style: field(f, "style"),
                    personality: {
                      ...person.profile.personality,
                      core_traits: field(f, "traits")
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean),
                    },
                    speech_style: {
                      ...person.profile.speech_style,
                      tone: field(f, "voice"),
                    },
                    appearance: {
                      ...person.profile.appearance,
                      ...Object.fromEntries(
                        [
                          "age_description",
                          "hair",
                          "eyes",
                          "clothing",
                          "other_details",
                        ].map((k) => [k, field(f, "appearance_" + k)]),
                      ),
                    },
                  };
                  const c = await api<Person>(
                    "/characters/" + person.id,
                    { profile: p, expected_version: person.profile_version },
                    "PATCH",
                  );
                  setPerson(c);
                  await changed();
                  if(reviewPortrait){setReviewPortrait(false);setPanel("portrait");setNotice("Appearance saved. Review it before requesting a new portrait.");}
                  else {setPanel(null);setNotice("Character saved. Existing scenes keep their snapshots.");}
                });
              }}
            >
              {[
                ["name", "Name", person.profile.name, 60],
                [
                  "short",
                  "One-line description",
                  person.profile.short_description,
                  500,
                ],
                ["wants", "What do they want?", person.profile.wants, 300],
                [
                  "traits",
                  "Core traits",
                  person.profile.personality?.core_traits?.join(", "),
                  1500,
                ],
                [
                  "voice",
                  "Speaking style",
                  person.profile.speech_style?.tone,
                  500,
                ],
                ["why", "Why it matters", person.profile.why_it_matters, 500],
                ["fear", "Fear or boundary", person.profile.fear, 300],
                [
                  "secret",
                  "Private information",
                  person.profile.private_information,
                  500,
                ],
                ["background", "Background", person.profile.backstory, 4000],
              ].map(([key, label, value, max]) => (
                <label key={String(key)}>
                  {label}
                  {key === "name" || key === "short" ? (
                    <input
                      name={String(key)}
                      defaultValue={String(value || "")}
                      maxLength={Number(max)}
                      required={key === "name"}
                    />
                  ) : (
                    <textarea
                      name={String(key)}
                      defaultValue={String(value || "")}
                      maxLength={Number(max)}
                      rows={key === "background" ? 4 : 2}
                    />
                  )}
                </label>
              ))}
              <details className="rh-details" open={reviewPortrait||undefined}>
                <summary>
                  Appearance & portrait style <span>＋</span>
                </summary>
                {[
                  "age_description",
                  "hair",
                  "eyes",
                  "clothing",
                  "other_details",
                ].map((k) => (
                  <label key={k}>
                    {k.replaceAll("_", " ")}
                    <input
                      name={"appearance_" + k}
                      defaultValue={person.profile.appearance?.[k] || ""}
                      maxLength={500}
                    />
                  </label>
                ))}
                <label>
                  Portrait style
                  <input
                    name="style"
                    defaultValue={person.profile.visual_style}
                    maxLength={500}
                  />
                </label>
              </details>
              <button className="rh-primary" disabled={busy}>
                Save character
              </button>
            </form>
          )}
          {panel === "refine" && (
            <>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const text = field(
                    new FormData(e.currentTarget),
                    "instruction",
                  );
                  void run(async () =>
                    setProposal(
                      await api<Proposal>(
                        "/characters/" + person.id + "/refine",
                        {
                          instruction: text,
                          expected_version: person.profile_version,
                        },
                      ),
                    ),
                  );
                }}
              >
                <label>
                  What should change?
                  <textarea
                    name="instruction"
                    required
                    maxLength={2000}
                    rows={4}
                    placeholder="Make her more reserved, but keep her appearance and background."
                  />
                </label>
                <button className="rh-secondary" disabled={busy}>
                  Preview changes
                </button>
              </form>
              {proposal && (
                <div className="mc-proposal">
                  <p>{proposal.explanation}</p>
                  {proposal.changes.map((c, i) => (
                    <section key={i}>
                      <small>{c.path}</small>
                      <p>
                        <del>
                          {Array.isArray(c.before)
                            ? c.before.join(", ")
                            : c.before}
                        </del>
                        <span> → </span>
                        <strong>
                          {Array.isArray(c.after)
                            ? c.after.join(", ")
                            : c.after}
                        </strong>
                      </p>
                    </section>
                  ))}
                  <button
                    className="rh-primary"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const c = await api<Person>(
                          "/characters/" + person.id + "/refine/confirm",
                          { proposal_id: proposal.proposal_id },
                        );
                        setPerson(c);
                        setProposal(null);
                        await changed();
                        setPanel(null);
                      })
                    }
                  >
                    Apply these changes
                  </button>
                </div>
              )}
            </>
          )}
          {panel === "portrait" && (
            <>
              <Picture character={person} large />
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const instruction = field(
                    new FormData(e.currentTarget),
                    "instruction",
                  );
                  void run(async () => {
                    await makePortrait(!!person.current_image_id, instruction);
                  });
                }}
              >
                <label>
                  What should change in the portrait?
                  <textarea
                    name="instruction"
                    rows={3}
                    maxLength={2000}
                    required={!!person.current_image_id}
                    placeholder="Change her hair to auburn. Keep her face and clothing."
                  />
                </label>
                <button className="rh-primary" disabled={busy || portraitGenerating}>
                  {portraitGenerating
                    ? "Initial portrait is still generating…"
                    : busy
                      ? "Creating a portrait…"
                      : person.current_image_id
                        ? "Edit portrait"
                        : "Generate portrait"}
                </button>
                <button
                  type="button"
                  className="rh-secondary mc-another"
                  disabled={busy || portraitGenerating}
                  onClick={() => run(() => makePortrait(false))}
                >
                  Try another portrait
                </button>
              </form>
              <h3 className="mc-versions-heading">Portrait versions</h3>
              <div className="mc-portrait-grid">
                {portraits.map((p) => (
                  <section key={p.id}>
                    <img src={p.url} alt={"Portrait version " + p.version} />
                    <small>Version {p.version}</small>
                    <button
                      className="rh-secondary"
                      disabled={busy || person.current_image_id === p.id}
                      onClick={() =>
                        run(async () => {
                          await api(
                            `/characters/${person.id}/images/${p.id}/select`,
                            {},
                          );
                          await reloadPerson();
                          await changed();
                          setImageError("");
                        })
                      }
                    >
                      {person.current_image_id === p.id
                        ? "Selected"
                        : "Use this portrait"}
                    </button>
                  </section>
                ))}
              </div>
            </>
          )}
          {panel === "history" && (
            <div className="rh-version-list">
              {revisions.map((r) => (
                <article key={r.version}>
                  <h3>
                    Version {r.version} · {r.profile.name}
                  </h3>
                  <p>{r.change_summary}</p>
                  <p>{r.profile.short_description}</p>
                  <button
                    className="rh-secondary"
                    disabled={busy || r.version === person.profile_version}
                    onClick={() =>
                      run(async () => {
                        const c = await api<Person>(
                          "/characters/" + person.id + "/restore",
                          {
                            version: r.version,
                            expected_version: person.profile_version,
                          },
                        );
                        setPerson(c);
                        await changed();
                        setPanel(null);
                      })
                    }
                  >
                    {r.version === person.profile_version
                      ? "Current version"
                      : "Restore as a new version"}
                  </button>
                </article>
              ))}
            </div>
          )}
          {panel === "more" && (
            <div className="rh-more-menu">
              <button
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const c = await creator<Person>(
                      "/characters/" + person.id + "/duplicate",
                      { request_id: operation() },
                    );
                    setPerson(c);
                    await changed();
                    url("detail", c.id);
                  })
                }
              >
                Duplicate character <span>→</span>
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await creator(
                      "/characters/" + person.id + "/archive",
                      { archived: !person.archived },
                      "PATCH",
                    );
                    await changed();
                    setPanel(null);
                    url("library");
                  })
                }
              >
                {person.archived ? "Unarchive character" : "Archive character"}
              </button>
              <button
                className="rh-danger"
                disabled={busy}
                onClick={() => {
                  if (
                    confirm(
                      "Delete this character and their companion history? Saved rehearsal snapshots remain.",
                    )
                  )
                    void run(async () => {
                      await api(
                        "/characters/" + person.id,
                        undefined,
                        "DELETE",
                      );
                      await changed();
                      url("library");
                    });
                }}
              >
                Delete character
              </button>
            </div>
          )}
        </Panel>
      )}
    </>
  );
}

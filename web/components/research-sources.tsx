"use client";
import {useEffect,useRef,useState} from "react";
import {type Character} from "./api";
import {creator} from "./creator-api";
import styles from "./character-research.module.css";
const inFlight=(s?:string)=>["queued","identifying","searching","researching"].includes(s||"");
export function ResearchSources({character,onApplied}:{character:Character;onApplied?:(c:Character)=>void}){
  const [data,setData]=useState(character.research);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const guard=useRef(false);
  const path="/characters/"+encodeURIComponent(character.id)+"/research";
  useEffect(()=>{
    setData(character.research);setError("");
    if(!character.research || !inFlight(character.research.status))return;
    let alive=true,timer:ReturnType<typeof setTimeout>|undefined;
    async function tick(){
      try{
        const result=await creator<Character["research"]>(path);
        if(!alive)return;
        setData(result);
        if(inFlight(result?.status))timer=setTimeout(tick,2000);
      }catch{if(alive)timer=setTimeout(tick,5000);}
    }
    void tick();
    return()=>{alive=false;if(timer)clearTimeout(timer);};
  },[character.id,character.research?.status,character.profile_version]);
  async function apply(){
    if(guard.current)return;
    guard.current=true;setBusy(true);setError("");
    try{
      const c=await creator<Character>(path+"/apply",{});
      setData(c.research);onApplied?.(c);
    }catch(e){setError(e instanceof Error?e.message:"Could not apply research.");}
    finally{setBusy(false);guard.current=false;}
  }
  if(!data || data.status==="skipped")return null;
  const sources=data.sources||data.discovered_sources||[];
  if(inFlight(data.status))return <div className={styles.progress} role="status"><span className={styles.dot}/> {data.status==="searching"?"Finding sources…":data.status==="researching"?"Researching · Firecrawl":"Preparing research…"}</div>;
  if(data.status==="unavailable")return <p className={styles.sources}>Research unavailable · Profile saved</p>;
  const pending=data.status==="proposal";
  const stale=pending && data.base_version!==character.profile_version;
  return <div className={styles.sources}>
    {pending&&<div className={styles.update}><span>Research update ready</span>{onApplied&&!stale&&<button type="button" onClick={()=>void apply()} disabled={busy}>{busy?"Applying…":"Apply update"}</button>}</div>}
    {stale&&<small>Profile edited. Research will not overwrite your changes.</small>}
    {pending&&!onApplied&&<small>Review and apply in Characters.</small>}
    {error&&<p role="alert">{error}</p>}
    <details>
      <summary>Research sources · {sources.length} · Firecrawl</summary>
      {pending&&data.proposal&&<div className={styles.preview}><strong>Proposed profile</strong><p>{data.proposal.short_description}</p><p>{data.proposal.backstory}</p><p>{data.proposal.personality?.core_traits?.join(" · ")}</p><p>{data.proposal.speech_style?.tone}</p></div>}
      <small>Agent-reported references{!pending&&character.profile_version!==data.profile_version?" (earlier profile)":""}.</small>
      {sources.map(s=>{
        try{const u=new URL(s);if(u.protocol!=="https:")return null;
          return <a key={s} href={s} target="_blank" rel="noopener noreferrer">{u.hostname}{u.pathname!=="/"?u.pathname:""}</a>;
        }catch{return null;}
      })}
    </details>
  </div>;
}

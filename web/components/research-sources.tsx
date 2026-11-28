"use client";
import type {Character} from "./api";
import styles from "./character-research.module.css";
export function ResearchSources({character}:{character:Character}){
  const sources=character.research?.sources||[];
  if(!sources.length)return null;
  return <details className={styles.sources}>
    <summary>Research sources · {sources.length} · Firecrawl</summary>
    <small>Agent-reported references for initial profile{character.profile_version!==character.research?.profile_version?" (before edits)":""}.</small>
    {sources.map(s=>{
      try{const u=new URL(s);if(u.protocol!=="https:")return null;
        return <a key={s} href={s} target="_blank" rel="noopener noreferrer">{u.hostname}{u.pathname!=="/"?u.pathname:""}</a>;
      }catch{return null;}
    })}
  </details>;
}

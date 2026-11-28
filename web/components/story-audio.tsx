"use client";
import {useEffect,useRef,useState} from "react";
import type {Actor,Node,Block} from "./rehearsal-api";
import styles from "./story-audio.module.css";

type Status={enabled:boolean;narration:boolean};
type Playback={key:string;phase:"loading"|"playing";text:string};
type Failure={key:string;message:string};
const passageKey=(nodeId:string,blockId:string)=>nodeId+":"+blockId;

/** One player for the entire reader. Only a user's explicit click requests audio. */
export function useStoryAudio({sceneId,versionId,nodes,actors,language,enabled}:{
  sceneId?:string;versionId?:string;nodes:Node[];actors:Actor[];language:"en"|"zh";enabled:boolean;
}){
  const [status,setStatus]=useState<Status|null>(null);
  const [active,setActive]=useState<Playback|null>(null);
  const [error,setError]=useState<Failure|null>(null);
  const current=useRef<HTMLAudioElement|null>(null);
  const url=useRef("");
  const controller=useRef<AbortController|null>(null);
  const token=useRef(0);
  const activeRef=useRef<Playback|null>(null);
  const tr=(en:string,zh:string)=>language==="zh"?zh:en;
  const scope=enabled&&sceneId&&versionId?sceneId+":"+versionId:"";
  const scopeRef=useRef(scope);
  scopeRef.current=scope;

  function release(){
    controller.current?.abort();controller.current=null;
    const player=current.current;current.current=null;
    if(player){player.onended=null;player.onerror=null;player.pause();}
    if(url.current){URL.revokeObjectURL(url.current);url.current="";}
  }
  function stop(){
    token.current++;release();activeRef.current=null;setActive(null);
  }
  useEffect(()=>{
    setStatus(null);
    if(!scope)return;
    const c=new AbortController();
    fetch("/api/voice/audio/status",{cache:"no-store",signal:c.signal})
      .then(r=>r.ok?r.json():null)
      .then(s=>{if(!c.signal.aborted)setStatus(s);}).catch(()=>{});
    return ()=>c.abort();
  },[scope]);
  useEffect(()=>{
    stop();setError(null);
    return ()=>{token.current++;release();activeRef.current=null;};
  },[scope]);

  const available=(block:Block)=>{
    const actor=actors.find(a=>a.id===block.character_id);
    return !!(scope&&status?.enabled&&block.text.trim()&&
      (block.type==="dialogue"?actor?.voice_identity:status.narration));
  };
  // Continuing the story does not interrupt an unchanged paragraph; an edit,
  // reveal change to this paragraph, or removal from the visible branch does.
  const activeBlock=active?nodes.flatMap(n=>n.blocks.map(b=>({key:passageKey(n.id,b.id),block:b})))
    .find(p=>p.key===active.key)?.block:undefined;
  useEffect(()=>{
    if(active&&(!activeBlock||activeBlock.text!==active.text||!available(activeBlock)))stop();
  },[active?.key,active?.text,activeBlock?.text,!!activeBlock,status,scope]);

  async function toggle(nodeId:string,block:Block){
    if(!available(block)||!sceneId||!versionId)return;
    const key=passageKey(nodeId,block.id);
    if(activeRef.current?.key===key){stop();return;}
    stop();setError(null);
    const id=token.current, startingScope=scope;
    const isCurrent=()=>id===token.current&&scopeRef.current===startingScope;
    const update=(phase:Playback["phase"])=>{
      const state={key,phase,text:block.text};
      activeRef.current=state;setActive(state);
    };
    const fail=(message:string)=>{if(isCurrent()){stop();setError({key,message});}};
    update("loading");
    const c=new AbortController();controller.current=c;
    try{
      const r=await fetch("/api/voice/scenes/"+encodeURIComponent(sceneId)+"/audio",{
        method:"POST",headers:{"Content-Type":"application/json"},signal:c.signal,
        body:JSON.stringify({version_id:versionId,node_id:nodeId,block_id:block.id})
      });
      if(!r.ok){
        const d=await r.json().catch(()=>({}));
        throw new Error(typeof d.detail==="string"?d.detail:tr("Audio unavailable.","语音暂时不可用。"));
      }
      const blob=await r.blob();if(!isCurrent())return;
      url.current=URL.createObjectURL(blob);
      const player=new Audio(url.current);current.current=player;
      player.onended=()=>{if(isCurrent())stop();};
      player.onerror=()=>fail(tr("Audio playback failed.","语音播放失败。"));
      await player.play();
      if(isCurrent())update("playing");
    }catch(e){
      if(isCurrent())fail(e instanceof Error?e.message:tr("Audio unavailable.","语音暂时不可用。"));
    }
  }

  function button(nodeId:string,block:Block){
    if(!available(block))return null;
    const key=passageKey(nodeId,block.id);
    const phase=active?.key===key?active.phase:"idle";
    const name=block.type==="dialogue"?actors.find(a=>a.id===block.character_id)?.name||tr("character","角色"):tr("narration","旁白");
    const label=phase==="loading"?tr("Cancel audio for ","取消语音：")+name:
      phase==="playing"?tr("Stop audio for ","停止语音：")+name:tr("Play audio for ","播放语音：")+name;
    return <button type="button" className={styles.speaker+(phase!=="idle"?" "+styles.active:"")}
      aria-label={label} title={label} aria-pressed={phase!=="idle"}
      data-audio-phase={phase} data-audio-block={block.id}
      onClick={()=>void toggle(nodeId,block)}>
      {phase==="loading"?<span className={styles.spinner} aria-hidden="true"/>:
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {phase==="playing"?<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>:
            <><path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15 9a4 4 0 0 1 0 6M18 6a8 8 0 0 1 0 12"/></>}
        </svg>}
    </button>;
  }
  function message(nodeId:string,block:Block){
    const key=passageKey(nodeId,block.id);
    return error?.key===key?<div className={styles.error} role="alert">{error.message}</div>:null;
  }
  return {button,message};
}

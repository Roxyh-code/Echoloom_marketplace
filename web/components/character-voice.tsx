"use client";
import { useEffect, useRef, useState } from "react";
import styles from "./character-voice.module.css";

export type VoiceIdentity = {provider: "elevenlabs"; voice_id: string; name: string};
type Candidate = VoiceIdentity & {preview_url: string; reason: string; labels: Record<string,string>};
type Status = {enabled:boolean; voice:VoiceIdentity|null; profile_version:number;preview_synthesis?:boolean};
type Suggestions = {choices:Candidate[];reason:string;profile_version:number;sample_text?:string;sample_id?:string};
async function request<T>(path:string, method="GET", body?:unknown):Promise<T> {
  const r=await fetch("/api/voice"+path,{method,cache:"no-store",credentials:"same-origin",
    headers:body?{"Content-Type":"application/json"}:undefined,body:body?JSON.stringify(body):undefined});
  const data=await r.json();
  if(!r.ok) throw new Error(typeof data.detail==="string"?data.detail:"Voice service unavailable.");
  return data;
}
export function CharacterVoice({id, profileVersion}:{id:string;profileVersion:number}) {
  const [status,setStatus]=useState<Status|null>(null);
  const [choices,setChoices]=useState<Candidate[]>([]);
  const [selected,setSelected]=useState("");
  const [sample,setSample]=useState({text:"",id:""});
  const [method,setMethod]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [playing,setPlaying]=useState("");
  const [loadingVoice,setLoadingVoice]=useState("");
  const audio=useRef<HTMLAudioElement|null>(null);
  const objectUrl=useRef("");
  const previewRequest=useRef<AbortController|null>(null);
  const generation=useRef(0);
  const path="/characters/"+encodeURIComponent(id);
  function release(){
    previewRequest.current?.abort();previewRequest.current=null;
    if(audio.current){audio.current.onended=null;audio.current.onerror=null;audio.current.pause();audio.current=null;}
    if(objectUrl.current){URL.revokeObjectURL(objectUrl.current);objectUrl.current="";}
  }
  function stop(){release();setPlaying("");setLoadingVoice("");}
  async function suggest(token:number){
    stop();setBusy(true);setError("");
    try {
      const r=await request<Suggestions>(path+"/recommend","POST");
      if(generation.current!==token)return;
      setChoices(r.choices);setMethod(r.reason);setSelected(r.choices[0]?.voice_id||"");
      setSample({text:r.sample_text||"",id:r.sample_id||""});
      if(!r.choices.length)setError("At least three approved voices are required. Check the voice catalog.");
    }catch(e){if(generation.current===token)setError(e instanceof Error?e.message:"Voice matching failed.");}
    finally{if(generation.current===token)setBusy(false);}
  }
  useEffect(()=>{
    const token=++generation.current;
    setStatus(null);setChoices([]);setSelected("");setSample({text:"",id:""});setError("");setBusy(false);setPlaying("");setLoadingVoice("");
    void request<Status>(path).then(r=>{
      if(generation.current!==token)return;
      setStatus(r);
      if(r.enabled&&!r.voice)void suggest(token);
    }).catch(()=>{});
    return ()=>{generation.current++;release();};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[id,profileVersion]);
  async function preview(v:Candidate){
    if(playing===v.voice_id||loadingVoice===v.voice_id){stop();return;}
    stop();setError("");
    const ctrl=new AbortController();previewRequest.current=ctrl;
    try{
      let src=v.preview_url;
      if(status?.preview_synthesis){
        if(!sample.id)throw new Error("Match voices again to obtain a dialogue sample.");
        setLoadingVoice(v.voice_id);
        const r=await fetch("/api/voice"+path+"/preview",{method:"POST",signal:ctrl.signal,
          headers:{"Content-Type":"application/json"},body:JSON.stringify({voice_id:v.voice_id,expected_profile_version:profileVersion,sample_id:sample.id})});
        if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(typeof d.detail==="string"?d.detail:"Dialogue preview unavailable.");}
        const blob=await r.blob();
        if(ctrl.signal.aborted)return;
        src=URL.createObjectURL(blob);objectUrl.current=src;
      }
      if(ctrl.signal.aborted)return;
      const player=new Audio(src);audio.current=player;
      player.onended=()=>{if(audio.current===player)stop();};
      player.onerror=()=>{if(audio.current===player){stop();setError("Preview could not be played.");}};
      setLoadingVoice("");setPlaying(v.voice_id);
      await player.play();
    }catch(e){if(!ctrl.signal.aborted){stop();setError(e instanceof Error?e.message:"Preview unavailable.");}}
  }
  async function save(){
    if(!selected||busy)return;
    const token=generation.current;stop();setBusy(true);setError("");
    try{
      const r=await request<{voice:VoiceIdentity}>(path,"PUT",{voice_id:selected,expected_profile_version:profileVersion});
      if(generation.current!==token)return;
      setStatus(s=>s?{...s,voice:r.voice}:s);setChoices([]);
    }catch(e){if(generation.current===token)setError(e instanceof Error?e.message:"Could not save voice.");}
    finally{if(generation.current===token)setBusy(false);}
  }
  if(!status?.enabled)return null;
  return <section className={styles.section} aria-label="Voice identity">
    <span className="rh-eyebrow">VOICE IDENTITY · ELEVENLABS</span>
    <h3>A voice of their own</h3>
    <p className={styles.help}>Three voices matched to this character. Choose one to keep across stories.</p>
    {status.voice&&<p><strong>{status.voice.name}</strong> · Saved voice</p>}
    {busy&&<p className={styles.help} role="status">Matching or saving voice…</p>}
    {error&&<p className={styles.help} role="alert">{error}</p>}
    {!!choices.length&&status.preview_synthesis&&sample.text&&<blockquote className={styles.sample} aria-label="Shared dialogue sample">“{sample.text}”</blockquote>}
    {!!choices.length&&!status.preview_synthesis&&<p className={styles.help}>Dialogue synthesis is off; previews use the provider's library samples.</p>}
    {choices.map((v,i)=><div key={v.voice_id} className={styles.card+(selected===v.voice_id?" "+styles.selected:"")}>
      <button type="button" className={styles.choice} aria-pressed={selected===v.voice_id} disabled={busy} onClick={()=>setSelected(v.voice_id)}>
        <span className={styles.mark} aria-hidden="true"/>
        <span className={styles.choiceText}><small>{i===0?"BEST MATCH":"ALTERNATIVE"}</small><strong>{v.name}</strong></span>
      </button>
      <p className={styles.help}>{v.reason}</p>
      <button type="button" className={"rh-secondary "+styles.preview} aria-label={"Preview "+v.name} onClick={()=>void preview(v)}>{loadingVoice===v.voice_id?"Preparing dialogue… · Cancel":playing===v.voice_id?"Stop preview":status.preview_synthesis?"▶ Hear dialogue":"▶ Library preview"}</button>
    </div>)}
    {!!choices.length&&<><p className={styles.help}>{method==="ai"?"AI-matched voices":"Metadata-based suggestions"}</p>
      <button className="rh-primary" type="button" disabled={busy||!selected} onClick={()=>void save()}>Confirm voice</button></>}
    {!choices.length&&!busy&&<button type="button" className="rh-secondary" onClick={()=>void suggest(generation.current)}>{status.voice?"Change voice":"Match voices"}</button>}
    <p className={styles.help}>Publishing shares your selected voice with future casts; existing stories retain their original voice.</p>
  </section>;
}

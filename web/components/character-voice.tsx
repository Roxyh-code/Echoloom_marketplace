"use client";
import { useEffect, useRef, useState } from "react";

export type VoiceIdentity = {provider: "elevenlabs"; voice_id: string; name: string};
type Candidate = VoiceIdentity & {preview_url: string; reason: string; labels: Record<string,string>};
type Status = {enabled:boolean; voice:VoiceIdentity|null; profile_version:number};
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
  const [method,setMethod]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [playing,setPlaying]=useState("");
  const audio=useRef<HTMLAudioElement|null>(null);
  const generation=useRef(0);
  const path="/characters/"+encodeURIComponent(id);
  function stop(){audio.current?.pause();audio.current=null;setPlaying("");}
  async function suggest(token:number){
    setBusy(true);setError("");
    try {
      const r=await request<{choices:Candidate[];reason:string;profile_version:number}>(path+"/recommend","POST");
      if(generation.current!==token)return;
      setChoices(r.choices);setMethod(r.reason);setSelected(r.choices[0]?.voice_id||"");
      if(!r.choices.length)setError("At least three approved voices are required. Check the voice catalog.");
    }catch(e){if(generation.current===token)setError(e instanceof Error?e.message:"Voice matching failed.");}
    finally{if(generation.current===token)setBusy(false);}
  }
  useEffect(()=>{
    const token=++generation.current;
    setStatus(null);setChoices([]);setSelected("");setError("");setBusy(false);
    void request<Status>(path).then(r=>{
      if(generation.current!==token)return;
      setStatus(r);
      if(r.enabled&&!r.voice)void suggest(token);
    }).catch(()=>{});
    return ()=>{generation.current++;audio.current?.pause();audio.current=null;};
    // Profile updates refresh recommendations but never silently replace a saved voice.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[id,profileVersion]);
  async function preview(v:Candidate){
    if(playing===v.voice_id){stop();return;}
    stop();const player=new Audio(v.preview_url);audio.current=player;
    player.onended=()=>{if(audio.current===player)stop();};
    player.onerror=()=>{if(audio.current===player){stop();setError("Preview could not be played.");}};
    setPlaying(v.voice_id);
    try{await player.play();}catch{if(audio.current===player){stop();setError("Preview unavailable.");}}
  }
  async function save(){
    if(!selected||busy)return;
    const token=generation.current;setBusy(true);setError("");
    try{
      const r=await request<{voice:VoiceIdentity}>(path,"PUT",{voice_id:selected,expected_profile_version:profileVersion});
      if(generation.current!==token)return;
      stop();setStatus(s=>s?{...s,voice:r.voice}:s);setChoices([]);
    }catch(e){if(generation.current===token)setError(e instanceof Error?e.message:"Could not save voice.");}
    finally{if(generation.current===token)setBusy(false);}
  }
  if(!status?.enabled)return null;
  return <section className="rh-details" style={{padding:"16px 0",marginTop:16}}>
    <span className="rh-eyebrow">VOICE IDENTITY · ELEVENLABS</span>
    <h3>A voice of their own</h3>
    <p className="rh-muted">Choose an existing voice matched to this character. Your choice stays with them across stories.</p>
    {status.voice&&<p><strong>{status.voice.name}</strong> · Saved voice</p>}
    {busy&&<p role="status">Matching or saving voice…</p>}
    {error&&<p role="alert">{error}</p>}
    {choices.map((v,i)=><div key={v.voice_id} style={{padding:12,margin:"10px 0",border:"1px solid #665477",borderRadius:10}}>
      <label style={{display:"flex",gap:10,alignItems:"center"}}>
        <input type="radio" name={"voice-"+id} checked={selected===v.voice_id} disabled={busy} onChange={()=>setSelected(v.voice_id)}/>
        <span><small className="rh-eyebrow">{i===0?"BEST MATCH":"ALTERNATIVE"}</small><br/><strong>{v.name}</strong></span>
      </label>
      <p className="rh-muted">{v.reason}</p>
      <button type="button" className="rh-secondary" onClick={()=>void preview(v)}>{playing===v.voice_id?"Stop preview":"▶ Preview voice"}</button>
    </div>)}
    {!!choices.length&&<><p className="rh-muted">{method==="ai"?"AI-matched voices":"Metadata-based suggestions"}</p>
      <button className="rh-primary" type="button" disabled={busy||!selected} onClick={()=>void save()}>Confirm voice</button></>}
    {!choices.length&&!busy&&<button type="button" className="rh-secondary" onClick={()=>void suggest(generation.current)}>{status.voice?"Change voice":"Match voices"}</button>}
    <p className="rh-muted">Publishing shares the selected voice with new story casts. Existing stories keep their original voice.</p>
  </section>;
}

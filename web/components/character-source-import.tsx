"use client";
import {useEffect,useState,useRef} from "react";

export function CharacterSourceImport({disabled,onImport}:{disabled:boolean;onImport:(text:string)=>void}) {
  const [available,setAvailable]=useState(false);
  const [open,setOpen]=useState(false);
  const [url,setUrl]=useState("");
  const [name,setName]=useState("");
  const [consent,setConsent]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [result,setResult]=useState<{description:string;source_url:string;truncated:boolean}|null>(null);
  const active=useRef<AbortController|null>(null);
  useEffect(()=>{
    let live=true;
    fetch("/api/character-import/status",{cache:"no-store",credentials:"same-origin"})
      .then(r=>r.ok?r.json():null).then(r=>{if(live)setAvailable(r?.available===true);}).catch(()=>{});
    return ()=>{live=false;active.current?.abort();};
  },[]);
  async function load(){
    if(active.current||disabled||!consent)return;
    const ctl=new AbortController();active.current=ctl;setBusy(true);setError("");setResult(null);
    try{
      const r=await fetch("/api/character-import",{method:"POST",credentials:"same-origin",signal:ctl.signal,
        headers:{"Content-Type":"application/json"},body:JSON.stringify({url,character_name:name,rights_confirmed:consent})});
      const data=await r.json();
      if(!r.ok)throw new Error(typeof data.detail==="string"?data.detail:"Import failed.");
      if(!ctl.signal.aborted)setResult(data);
    }catch(e){if(!ctl.signal.aborted)setError(e instanceof Error?e.message:"Import failed.");}
    finally{if(!ctl.signal.aborted){active.current=null;setBusy(false);}}
  }
  if(!available)return null;
  return <section style={{margin:"0 0 18px",padding:14,border:"1px solid #665184",borderRadius:10}}>
    <button type="button" className="rh-text-button" disabled={disabled} onClick={()=>setOpen(v=>!v)} aria-expanded={open}>Import character from a website {open?"−":"+"}</button>
    {open&&<div style={{display:"grid",gap:10,marginTop:12}}>
      <small>Powered by Firecrawl · use a public source you have permission to use.</small>
      <label>Character name<input type="text" maxLength={80} value={name} disabled={disabled||busy} onChange={e=>{setName(e.target.value);setResult(null);}}/></label>
      <label>Source URL<input type="url" maxLength={1000} placeholder="https://example.com/character" value={url} disabled={disabled||busy} onChange={e=>{setUrl(e.target.value);setResult(null);}}/></label>
      <label style={{display:"flex",alignItems:"flex-start",gap:8}}><input type="checkbox" checked={consent} disabled={disabled||busy} onChange={e=>setConsent(e.target.checked)} style={{width:18,height:18,flexShrink:0}}/>I have permission to use this source and understand it does not grant commercial publishing rights.</label>
      <button type="button" className="rh-secondary" disabled={disabled||busy||!name.trim()||!url.trim()||!consent} onClick={()=>void load()}>{busy?"Reading source…":"Import source"}</button>
      {error&&<p role="alert">{error}</p>}
      {result&&<><small>Review the extracted material before replacing your description.{result.truncated?" Source shortened to fit the character input limit.":""}</small>
        <textarea aria-label="Imported source preview" readOnly value={result.description} rows={5}/>
        <button type="button" className="rh-primary" disabled={disabled||!consent} onClick={()=>{onImport(result.description);setOpen(false);setResult(null);}}>Use imported description</button></>}
    </div>}
  </section>;
}

"use client";
import {useEffect,useRef,useState} from "react";
import type {Character} from "./api";
import {creator} from "./creator-api";
import styles from "./portrait-recovery.module.css";

type State="ready"|"pending"|"interrupted"|"failed"|"missing"|"archived";
export function PortraitRecovery({character,onRecovered}:{character:Character;onRecovered:(c:Character)=>void}){
  const [state,setState]=useState<State|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const active=useRef(true);
  const guard=useRef(false);
  const callback=useRef(onRecovered);
  callback.current=onRecovered;
  const path="/characters/"+encodeURIComponent(character.id)+"/portrait";
  useEffect(()=>{
    let mounted=true;
    active.current=true;
    setState(null);setError("");setBusy(false);guard.current=false;
    let timer:ReturnType<typeof setTimeout>|undefined;
    async function check(){
      try{
        const r=await creator<{state:State}>(path+"/status");
        if(!mounted)return;
        setState(r.state);
        if(r.state==="ready"&&!character.current_image_id){
          const fresh=await creator<Character[]>("/characters");
          const c=fresh.find(c=>c.id===character.id);
          if(mounted&&c?.current_image_id)callback.current(c);
        }
        if(r.state==="pending")timer=setTimeout(check,2000);
      }catch{
        if(mounted)setState("missing");
      }
    }
    void check();
    return()=>{mounted=false;active.current=false;if(timer)clearTimeout(timer);};
  },[character.id,character.current_image_id]);
  async function recover(){
    if(guard.current)return;
    guard.current=true;setBusy(true);setError("");
    try{
      const c=await creator<Character>(path+"/recover",{});
      if(active.current){
        if(!c.current_image_id)throw new Error("Portrait not selected yet. Retry.");
        callback.current(c);setState("ready");
      }
    }catch(e){if(active.current)setError(e instanceof Error?e.message:"Portrait generation failed.");}
    finally{guard.current=false;if(active.current)setBusy(false);}
  }
  if(state==="ready"||state==="archived"||state===null)return null;
  return <section className={styles.panel} aria-label="Portrait recovery">
    <p className={styles.label}>{busy||state==="pending"?"Generating portrait…":state==="interrupted"?"Portrait generation interrupted":state==="failed"?"Portrait generation failed":"Portrait unavailable"}</p>
    <p className={styles.help}>Your character is saved. Only the portrait needs attention.</p>
    {state!=="pending"&&<button type="button" className={styles.button} disabled={busy} onClick={()=>void recover()}>{busy?"Generating…":"Retry portrait"}</button>}
    {error&&<p role="alert" className={styles.error}>{error}</p>}
  </section>;
}

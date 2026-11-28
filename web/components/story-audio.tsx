"use client";
import {useEffect,useRef,useState} from "react";
import type {Actor,Node} from "./rehearsal-api";
type Passage={node_id:string;block_id:string;name:string;text:string};
type Status={enabled:boolean;narration:boolean};
export function StoryAudio({sceneId,versionId,nodes,actors,language}:{sceneId:string;versionId:string;nodes:Node[];actors:Actor[];language:"en"|"zh"}){
  const [status,setStatus]=useState<Status|null>(null);
  const [active,setActive]=useState("");
  const [phase,setPhase]=useState<"idle"|"loading"|"playing">("idle");
  const [error,setError]=useState("");
  const current=useRef<HTMLAudioElement|null>(null);
  const url=useRef("");
  const controller=useRef<AbortController|null>(null);
  const token=useRef(0);
  const tr=(en:string,zh:string)=>language==="zh"?zh:en;
  const passages:Passage[]=nodes.flatMap(n=>n.blocks.flatMap(b=>{
    const actor=actors.find(a=>a.id===b.character_id);
    return (b.type==="dialogue"?actor?.voice_identity:status?.narration)?[{
      node_id:n.id,block_id:b.id,name:b.type==="dialogue"?actor?.name||"":tr("Narrator","旁白"),text:b.text
    }]:[];
  }));
  const signature=JSON.stringify([sceneId,versionId,passages,actors.map(a=>a.voice_identity)]);
  function release(){
    controller.current?.abort();controller.current=null;
    const player=current.current;current.current=null;
    if(player){player.onended=null;player.onerror=null;player.pause();}
    if(url.current){URL.revokeObjectURL(url.current);url.current="";}
  }
  function stop(){token.current++;release();setActive("");setPhase("idle");}
  useEffect(()=>{
    const c=new AbortController();
    fetch("/api/voice/audio/status",{cache:"no-store",signal:c.signal}).then(r=>r.ok?r.json():null)
      .then(s=>{if(!c.signal.aborted)setStatus(s);}).catch(()=>{});
    return ()=>c.abort();
  },[]);
  useEffect(()=>{stop();setError("");return ()=>{token.current++;release();};},[signature]);
  async function play(queue:Passage[]){
    stop();setError("");const id=token.current;
    for(const p of queue){
      if(id!==token.current)return;
      setActive(p.block_id);setPhase("loading");
      const c=new AbortController();controller.current=c;
      try{
        const r=await fetch("/api/voice/scenes/"+encodeURIComponent(sceneId)+"/audio",{
          method:"POST",headers:{"Content-Type":"application/json"},signal:c.signal,
          body:JSON.stringify({version_id:versionId,node_id:p.node_id,block_id:p.block_id})
        });
        if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(typeof d.detail==="string"?d.detail:"Audio unavailable.");}
        const blob=await r.blob();if(id!==token.current)return;
        url.current=URL.createObjectURL(blob);
        const player=new Audio(url.current);current.current=player;
        setPhase("playing");
        await new Promise<void>((resolve,reject)=>{
          player.onended=()=>resolve();player.onerror=()=>reject(new Error("Audio playback failed."));
          c.signal.addEventListener("abort",()=>resolve(),{once:true});
          void player.play().catch(reject);
        });
        if(id!==token.current)return;
        release();
      }catch(e){if(id===token.current){setError(e instanceof Error?e.message:"Audio unavailable.");stop();}return;}
    }
    if(id===token.current)stop();
  }
  if(!status?.enabled||!passages.length)return null;
  return <section style={{margin:"10px 0 16px",padding:14,border:"1px solid #665477",borderRadius:12}} aria-label="Story audio">
    <span className="rh-eyebrow">ELEVENLABS · {tr("AUDIO STORY","有声剧情")}</span>
    <p className="rh-muted">{tr("Listen to revealed passages using saved character voices. Audio is generated only when played.","使用角色已保存的声音播放已读片段，仅在点击播放时生成语音。")}</p>
    <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
      <button type="button" className="rh-secondary" onClick={()=>phase==="idle"?void play(passages):stop()}>
        {phase==="idle"?tr("▶ Listen to story","▶ 播放故事"):tr("Stop","停止")}
      </button>
      {phase!=="idle"&&<small role="status">{phase==="loading"?tr("Preparing audio…","正在准备语音…"):tr("Playing","播放中")} · {passages.find(p=>p.block_id===active)?.name}</small>}
    </div>
    <details style={{marginTop:10}}><summary>{tr("Choose a passage","选择片段")}</summary>
      {passages.map(p=><button key={p.node_id+":"+p.block_id} type="button" className="rh-secondary" style={{display:"block",width:"100%",marginTop:6,textAlign:"left"}} onClick={()=>void play([p])}>
        {p.name} · {p.text.slice(0,60)}{p.text.length>60?"…":""}
      </button>)}
    </details>
    {error&&<p role="alert">{error}</p>}
  </section>;
}

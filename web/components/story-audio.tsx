"use client";
import { useEffect, useRef, useState } from "react";

export function useStoryAudio(scope: string) {
  const [available, setAvailable] = useState(false);
  const [playing, setPlaying] = useState("");
  const [error, setError] = useState("");
  const audio = useRef<HTMLAudioElement | null>(null);
  const url = useRef("");
  const controller = useRef<AbortController | null>(null);
  function stop() {
    controller.current?.abort();
    controller.current = null;
    audio.current?.pause();
    audio.current = null;
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = "";
  }
  useEffect(() => {
    let active = true;
    fetch("/api/story-audio/status", {cache:"no-store", credentials:"same-origin"})
      .then(r => r.ok ? r.json() : null).then(r => {if(active) setAvailable(r?.available === true);}).catch(()=>{});
    return () => {active = false; stop();};
  }, [scope]);
  useEffect(() => {setPlaying(""); setError("");}, [scope]);
  async function play(scene: string, version: string, block: string, count: number) {
    const same = playing === block;
    stop(); setPlaying(""); setError("");
    if (same) return;
    const ctl = new AbortController(); controller.current = ctl; setPlaying(block);
    try {
      const r = await fetch("/api/story-audio/" + encodeURIComponent(scene), {
        method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json"},
        signal:ctl.signal, body:JSON.stringify({version_id:version,block_id:block,sentence_count:count})
      });
      if (!r.ok) {const e = await r.json().catch(()=>null); throw new Error(e?.detail || "Audio unavailable");}
      const blob = await r.blob();
      if (ctl.signal.aborted) return;
      url.current = URL.createObjectURL(blob);
      const player = new Audio(url.current); audio.current = player;
      player.onended = () => {if(controller.current===ctl){stop();setPlaying("");}};
      player.onerror = () => {if(controller.current===ctl){stop();setPlaying("");setError("Audio playback failed.");}};
      await player.play();
    } catch(e) {
      if (!ctl.signal.aborted) {stop();setPlaying("");setError(e instanceof Error ? e.message : "Audio unavailable");}
    }
  }
  return {available, playing, error, play};
}

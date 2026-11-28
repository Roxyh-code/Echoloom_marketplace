"use client";
import {useId} from "react";
/** Original decorative placeholder, not a likeness or generated portrait. */
export function PortraitPlaceholder({name}:{name:string}){
  const id=useId().replace(/:/g,"");
  const palettes=[["#21192f","#a889cc"],["#19282c","#82b8b1"],["#2b2025","#c7a27d"],["#252a3b","#94a9d9"]];
  const index=Array.from(name).reduce((n,c)=>(n+c.codePointAt(0)!)%palettes.length,0);
  const [bg,accent]=palettes[index];
  return <svg viewBox="0 0 240 320" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustrated portrait placeholder" style={{display:"block",background:bg}}>
    <defs><radialGradient id={id}><stop stopColor={accent} stopOpacity=".26"/><stop offset="1" stopColor={bg}/></radialGradient></defs>
    <rect width="240" height="320" fill={bg}/><rect width="240" height="320" fill={"url(#"+id+")"}/>
    <g fill="none" stroke={accent} strokeOpacity=".55"><rect x="13" y="13" width="214" height="294" rx="14"/><path d="M30 160V112a90 90 0 0 1 180 0v48"/><circle cx="120" cy="117" r="67" strokeDasharray="3 7"/><path d="M120 25l6 12-6 12-6-12zM25 282l5 8-5 8-5-8zM215 282l5 8-5 8-5-8z"/></g>
    <path d="M44 258c6-53 30-78 52-90-19-11-32-31-32-56 0-37 25-62 56-62s56 25 56 62c0 25-13 45-32 56 22 12 46 37 52 90z" fill={bg} stroke={accent} strokeOpacity=".8" strokeWidth="2"/>
    <path d="M96 171l24 34 24-34M120 205v53" stroke={accent} fill="none" strokeOpacity=".7"/>
    <text x="120" y="288" fill={accent} textAnchor="middle" fontSize="11" letterSpacing="2">PORTRAIT PENDING</text>
  </svg>;
}

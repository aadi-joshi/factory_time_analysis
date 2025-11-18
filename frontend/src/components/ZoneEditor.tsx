import React, { useEffect, useRef, useState } from 'react';
import { fetchFirstFrame, saveZones, ZonePoint, Zone } from '../hooks/api';

interface Props { videoId:number; onSaved:(zones:Zone[])=>void; }

interface DraftZone { name:string; points:ZonePoint[]; }

export const ZoneEditor:React.FC<Props> = ({ videoId, onSaved }) => {
  const canvasRef = useRef<HTMLCanvasElement|null>(null);
  const [img, setImg] = useState<HTMLImageElement|null>(null);
  const [zones,setZones] = useState<DraftZone[]>([]);
  const [current,setCurrent] = useState<DraftZone|undefined>();

  useEffect(()=>{ (async()=>{ const blob = await fetchFirstFrame(videoId); const url = URL.createObjectURL(blob); const im = new Image(); im.onload=()=>setImg(im); im.src=url; })(); },[videoId]);

  useEffect(()=>{ if(!img || !canvasRef.current) return; const c = canvasRef.current; c.width = img.width; c.height = img.height; const ctx = c.getContext('2d')!; ctx.drawImage(img,0,0); drawOverlay(); },[img,zones,current]);

  function drawOverlay(){ if(!canvasRef.current || !img) return; const ctx = canvasRef.current.getContext('2d')!; ctx.clearRect(0,0,canvasRef.current.width, canvasRef.current.height); ctx.drawImage(img,0,0); ctx.lineWidth = 1; zones.forEach(z=>{ ctx.strokeStyle='#6fcf97'; ctx.fillStyle='rgba(111,207,151,0.15)'; ctx.beginPath(); z.points.forEach((p,i)=>{ if(i===0) ctx.moveTo(p.x,p.y); else ctx.lineTo(p.x,p.y); }); if(z.points.length>2) ctx.closePath(); ctx.stroke(); ctx.fill(); }); if(current){ ctx.strokeStyle='#e0b656'; ctx.beginPath(); current.points.forEach((p,i)=>{ if(i===0) ctx.moveTo(p.x,p.y); else ctx.lineTo(p.x,p.y); }); ctx.stroke(); }
  }

  function handleClick(e:React.MouseEvent){ if(!canvasRef.current) return; const rect = canvasRef.current.getBoundingClientRect(); const x = e.clientX - rect.left; const y = e.clientY - rect.top; setCurrent(c=> c? {...c, points:[...c.points,{x,y}]} : { name:`Zone ${zones.length+1}`, points:[{x,y}]}); }
  function finishPolygon(){ if(current && current.points.length>=3){ setZones(z=>[...z,current]); setCurrent(undefined);} }
  async function save(){ const saved = await saveZones(videoId, zones.map(z=>({name:z.name, points:z.points}))); onSaved(saved); }

  return <div style={{padding:'6px'}}>
    <div style={{fontSize:12, marginBottom:4}}>Zone Editor: Click to add points, Finish when &gt;=3 points.</div>
    <canvas ref={canvasRef} style={{border:'1px solid #333', cursor:'crosshair'}} onClick={handleClick}></canvas>
    <div style={{marginTop:6, display:'flex', gap:6}}>
      <button onClick={finishPolygon} disabled={!current || current.points.length<3}>Finish Polygon</button>
      <button onClick={()=>{ setCurrent(undefined); }} disabled={!current}>Cancel Current</button>
      <button onClick={()=>{ setZones([]); setCurrent(undefined); }}>Clear All</button>
      <button onClick={save} disabled={!zones.length}>Save Zones</button>
    </div>
  </div>;
};

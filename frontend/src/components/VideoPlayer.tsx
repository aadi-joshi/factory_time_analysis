import React, { useEffect, useRef, useState } from 'react';
import { fetchFrame, fetchFrameTracks, FrameData } from '../hooks/api';
import { Zone } from '../hooks/api';

interface Props { videoId:number; totalFrames:number; fps:number; zones:Zone[]; }

export const VideoPlayer:React.FC<Props> = ({ videoId, totalFrames, fps, zones }) => {
  const [frame,setFrame] = useState(0);
  const [playing,setPlaying] = useState(false);
  const [seeking,setSeeking] = useState(false);
  const [frameImg,setFrameImg] = useState<string|undefined>();
  const [frameData,setFrameData] = useState<FrameData|undefined>();
  const canvasRef = useRef<HTMLCanvasElement|null>(null);

  // playback loop
  useEffect(()=>{ let t: number|undefined; if(playing && !seeking){ t = window.setInterval(()=>{ setFrame(f=> (f+1< totalFrames? f+1 : 0)); }, 1000/Math.max(fps,1)); } return ()=>{ if(t) clearInterval(t); }; },[playing, fps, totalFrames, seeking]);
  // fetch only target frame, cancelling previous pending by flag
  useEffect(()=>{ let cancelled=false; (async()=>{ const blob = await fetchFrame(videoId, frame); if(cancelled) return; setFrameImg(URL.createObjectURL(blob)); const fd = await fetchFrameTracks(videoId, frame); if(cancelled) return; setFrameData(fd); setSeeking(false); })(); return ()=>{ cancelled=true; }; },[videoId, frame]);
  useEffect(()=>{ if(!frameImg) return; const img = new Image(); img.onload=()=>{ if(canvasRef.current){ canvasRef.current.width = img.width; canvasRef.current.height = img.height; const ctx = canvasRef.current.getContext('2d')!; ctx.drawImage(img,0,0); drawOverlay(ctx); } }; img.src = frameImg; },[frameImg, frameData]);

  function drawOverlay(ctx:CanvasRenderingContext2D){ if(!frameData) return; // zones with thicker outline
    frameData.zones.forEach(z=>{ ctx.strokeStyle='#4caf50'; ctx.lineWidth=2; ctx.beginPath(); z.points.forEach((p,i)=>{ if(i===0) ctx.moveTo(p.x,p.y); else ctx.lineTo(p.x,p.y); }); if(z.points.length>2) ctx.closePath(); ctx.globalAlpha=0.25; ctx.fillStyle='#4caf50'; ctx.fill(); ctx.globalAlpha=1; ctx.stroke(); });
    frameData.persons.forEach(p=>{ const [x,y,w,h] = p.bbox; ctx.lineWidth=2; const color = p.value_added? '#00e676':'#ff5252'; ctx.strokeStyle = color; ctx.strokeRect(x,y,w,h); ctx.globalAlpha=0.15; ctx.fillStyle = color; ctx.fillRect(x,y,w,h); ctx.globalAlpha=1; ctx.font='12px Courier New'; ctx.fillStyle='#ffffff';
      const label = `#${p.internal_track_id} ${p.display_name}`; const textWidth = ctx.measureText(label).width + 6; const textHeight = 14; ctx.fillStyle='rgba(0,0,0,0.6)'; ctx.fillRect(x, y - textHeight, textWidth, textHeight); ctx.fillStyle='#fff'; ctx.fillText(label, x+3, y-4);
    });
  }

  return <div style={{display:'flex', flexDirection:'column', height:'100%'}}>
    <div className="videoArea">
      <canvas ref={canvasRef} style={{maxWidth:'100%', maxHeight:'100%'}}></canvas>
    </div>
    <div className="controls">
      <button onClick={()=>setPlaying(p=>!p)}>{playing? 'Pause':'Play'}</button>
      <button onClick={()=>setFrame(f=> Math.max(0,f-1))}>Prev</button>
      <button onClick={()=>setFrame(f=> Math.min(totalFrames-1,f+1))}>Next</button>
      <input type="range" min={0} max={totalFrames-1} value={frame} onChange={e=>{ setSeeking(true); setPlaying(false); setFrame(parseInt(e.target.value)); }} style={{flex:1}} />
      <span style={{fontSize:11}}>Frame {frame}/{totalFrames-1}</span>
    </div>
    <div className="frameInfo">
      {frameData && frameData.persons.map(p=> <span key={p.person_id} style={{marginRight:12}}>{p.display_name}:{p.value_added? 'VA':'NVA'}</span>)}
    </div>
  </div>;
};

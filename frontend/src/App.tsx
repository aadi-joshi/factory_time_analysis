import React, { useEffect, useState } from 'react';
import { listVideos, VideoMeta, getZones, processVideo, listPersons, fetchSummary, exportSummaryCSV, Zone } from './hooks/api';
import { VideoUpload } from './components/VideoUpload';
import { ZoneEditor } from './components/ZoneEditor';
import { VideoPlayer } from './components/VideoPlayer';
import { PersonList } from './components/PersonList';
import { SummaryTable } from './components/SummaryTable';
import { SummaryCharts } from './components/SummaryCharts';

export default function App(){
  const [videos,setVideos] = useState<VideoMeta[]>([]);
  const [active,setActive] = useState<VideoMeta|undefined>();
  const [zones,setZones] = useState<Zone[]>([]);
  const [showZoneEditor,setShowZoneEditor] = useState(false);
  const [persons,setPersons] = useState<any[]>([]);
  const [tab,setTab] = useState<'people'|'zones'|'summary'>('people');
  const [processing,setProcessing] = useState(false);

  useEffect(()=>{ listVideos().then(setVideos); },[]);
  useEffect(()=>{ if(active){ getZones(active.id).then(setZones); listPersons(active.id).then(setPersons);} },[active]);

  async function startProcess(){ if(!active) return; setProcessing(true); try { await processVideo(active.id); const updatedPersons = await listPersons(active.id); setPersons(updatedPersons);} finally { setProcessing(false);} }
  async function refreshPersons(){ if(active){ listPersons(active.id).then(setPersons); } }
  async function exportCSV(){ if(!active) return; const csv = await exportSummaryCSV(active.id); const blob = new Blob([csv], {type:'text/csv'}); const a = document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=`video_${active.id}_summary.csv`; a.click(); }
  async function refreshSummary(){ if(active){ const list = await fetchSummary(active.id); setPersons(list); } }

  return <div>
    <div className="header">
      <h1>Factory Time Analyzer</h1>
      <div style={{marginLeft:16, display:'flex', gap:8, alignItems:'center'}}>
        <select value={active?.id || ''} onChange={e=>{ const v = videos.find(x=> x.id===Number(e.target.value)); setActive(v); }} style={{background:'#181818', color:'#ddd', border:'1px solid #333'}}>
          <option value=''>Select Video</option>
          {videos.map(v=> <option key={v.id} value={v.id}>{v.original_name}</option>)}
        </select>
        <button onClick={()=>listVideos().then(setVideos)}>Refresh Videos</button>
        {active && <button onClick={()=>setShowZoneEditor(s=>!s)} disabled={processing}>{showZoneEditor? 'Close Zones':'Define Zones'}</button>}
        {active && !showZoneEditor && <button onClick={startProcess} disabled={processing || !zones.length}>{processing? 'Processing...':'Process Video'}</button>}
      </div>
    </div>
    <VideoUpload onUploaded={v=>{ setVideos(vs=>[...vs,v]); setActive(v); }} />
    <div className="container">
      <div className="leftPane">
        {active && !showZoneEditor && <VideoPlayer videoId={active.id} totalFrames={active.frame_count} fps={active.fps} zones={zones} />}
        {active && showZoneEditor && <ZoneEditor videoId={active.id} onSaved={(zs)=>{ setZones(zs); setShowZoneEditor(false); }} />}
        {!active && <div style={{padding:12, fontSize:12}}>Upload or select a video (e.g. video.mp4) to begin.</div>}
      </div>
      <div className="rightPane">
        <div className="tabs">
          <div className={`tab ${tab==='people'?'active':''}`} onClick={()=>{ setTab('people'); refreshPersons(); }}>People</div>
          <div className={`tab ${tab==='zones'?'active':''}`} onClick={()=>{ setTab('zones'); }}>Zones</div>
          <div className={`tab ${tab==='summary'?'active':''}`} onClick={()=>{ setTab('summary'); refreshSummary(); }}>Summary</div>
        </div>
        {tab==='people' && active && <PersonList videoId={active.id} persons={persons} onUpdate={setPersons} />}
        {tab==='zones' && <div style={{padding:8}}>{zones.map(z=> <div key={z.id}>{z.name} ({z.points.length} pts)</div>)}</div>}
        {tab==='summary' && active && <div style={{display:'flex', flexDirection:'column', gap:12}}>
          <SummaryTable persons={persons} onExport={exportCSV} />
          <SummaryCharts videoId={active.id} />
        </div>}
      </div>
    </div>
  </div>;
}

export interface VideoMeta { id:number; filename:string; original_name:string; fps:number; frame_count:number; duration_seconds:number; }
export interface ZonePoint { x:number; y:number; }
export interface Zone { id:number; name:string; points:ZonePoint[]; }
export interface PersonSummary { person_id:number; internal_track_id:number; name:string; total_time_seconds:number; value_added_seconds:number; non_value_added_seconds:number; value_added_ratio:number; }
export interface FramePerson { person_id:number; display_name:string; internal_track_id:number; frame_index:number; value_added:boolean; bbox:number[]; }
export interface FrameData { frame_index:number; persons:FramePerson[]; zones:Zone[]; }

const BASE = 'http://localhost:8000';

export async function uploadVideo(file:File):Promise<VideoMeta>{
  const fd = new FormData(); fd.append('file', file);
  const r = await fetch(`${BASE}/api/videos/`, { method:'POST', body:fd });
  if(!r.ok) throw new Error('Upload failed');
  return r.json();
}
export async function listVideos():Promise<VideoMeta[]>{
  const r = await fetch(`${BASE}/api/videos/`); return r.json();
}
export async function fetchFirstFrame(videoId:number):Promise<Blob>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/first-frame`); if(!r.ok) throw new Error('frame'); return r.blob();
}
export async function saveZones(videoId:number, zones:{name:string; points:ZonePoint[]}[]):Promise<Zone[]>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/zones`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(zones)}); if(!r.ok) throw new Error('zones'); return r.json();
}
export async function getZones(videoId:number):Promise<Zone[]>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/zones`); return r.json();
}
export async function processVideo(videoId:number){
  const r = await fetch(`${BASE}/api/videos/${videoId}/process`, { method:'POST' }); if(!r.ok) throw new Error('process'); return r.json();
}
export async function fetchFrame(videoId:number, frame:number):Promise<Blob>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/frame/${frame}`); if(!r.ok) throw new Error('frame'); return r.blob();
}
export async function fetchFrameTracks(videoId:number, frame:number):Promise<FrameData>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/tracks/frame/${frame}`); if(!r.ok) throw new Error('tracks'); return r.json();
}
export async function listPersons(videoId:number):Promise<PersonSummary[]>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/persons`); return r.json();
}
export async function renamePerson(videoId:number, personId:number, name:string):Promise<PersonSummary>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/persons/${personId}`, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name}) }); if(!r.ok) throw new Error('rename'); return r.json();
}
export async function mergePersons(videoId:number, from_id:number, into_id:number):Promise<PersonSummary[]>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/merge-persons`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({from_id, into_id}) }); if(!r.ok) throw new Error('merge'); return r.json();
}
export async function fetchSummary(videoId:number):Promise<PersonSummary[]>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/summary`); return r.json();
}
export async function exportSummaryCSV(videoId:number):Promise<string>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/export-summary`); if(!r.ok) throw new Error('csv'); return r.text();
}
export async function fetchPersonThumbnail(videoId:number, personId:number):Promise<Blob>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/persons/${personId}/thumbnail`);
  if(!r.ok) throw new Error('thumbnail');
  return r.blob();
}
export async function fetchAnalytics(videoId:number):Promise<any>{
  const r = await fetch(`${BASE}/api/videos/${videoId}/analytics`); if(!r.ok) throw new Error('analytics'); return r.json();
}

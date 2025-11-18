import React, { useState, useEffect } from 'react';
import { PersonSummary, renamePerson, mergePersons, fetchPersonThumbnail } from '../hooks/api';

interface Props { videoId:number; persons:PersonSummary[]; onUpdate:(list:PersonSummary[])=>void; }

export const PersonList:React.FC<Props> = ({ videoId, persons, onUpdate }) => {
  const [renameId,setRenameId] = useState<number|undefined>();
  const [newName,setNewName] = useState('');
  const [mergeFrom,setMergeFrom] = useState<number|undefined>();
  const [mergeInto,setMergeInto] = useState<number|undefined>();

  const [thumbs,setThumbs] = useState<Record<number,string>>({});

  useEffect(()=>{ // load thumbnails lazily
    (async()=>{
      const next:Record<number,string> = {...thumbs};
      for(const p of persons){
        if(!next[p.person_id]){
          try { const blob = await fetchPersonThumbnail(videoId, p.person_id); next[p.person_id] = URL.createObjectURL(blob); } catch(_) { /* ignore */ }
        }
      }
      setThumbs(next);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[persons, videoId]);

  async function doRename(){ if(!renameId) return; const updated = await renamePerson(videoId, renameId, newName); onUpdate(persons.map(p=> p.person_id===updated.person_id? updated : p)); setRenameId(undefined); setNewName(''); }
  async function doMerge(){ if(mergeFrom && mergeInto && mergeFrom!==mergeInto){ const merged = await mergePersons(videoId, mergeFrom, mergeInto); onUpdate(merged); setMergeFrom(undefined); setMergeInto(undefined);} }

  return <div className="list">
    {persons.map(p=> <div key={p.person_id} className="listItem" style={{display:'flex', alignItems:'center', gap:8}}>
      {thumbs[p.person_id] && <img src={thumbs[p.person_id]} alt={p.name} style={{width:48, height:48, objectFit:'cover', border:'2px solid #333', borderRadius:4}} />}
      <div style={{flex:1}}>
        <span style={{color:'#6fcf97'}}>#{p.internal_track_id}</span> {p.name} VA% {(p.value_added_ratio*100).toFixed(1)} Time VA {p.value_added_seconds.toFixed(1)}s / NVA {p.non_value_added_seconds.toFixed(1)}s
      </div>
      <div style={{display:'flex', gap:4}}>
        <button onClick={()=>{ setRenameId(p.person_id); setNewName(p.name); }}>Rename</button>
        <button onClick={()=>{ if(!mergeFrom) setMergeFrom(p.person_id); else setMergeInto(p.person_id); }}>Merge</button>
      </div>
    </div>)}
    {renameId && <div style={{marginTop:6}}>
      <input className="inputInline" value={newName} onChange={e=>setNewName(e.target.value)} />
      <button onClick={doRename}>Save</button>
      <button onClick={()=>setRenameId(undefined)}>Cancel</button>
    </div>}
    {(mergeFrom && !mergeInto) && <div style={{marginTop:6}}>Select target person to merge into...</div>}
    {(mergeFrom && mergeInto) && <div style={{marginTop:6}}>
      Merge {mergeFrom} -&gt; {mergeInto} <button onClick={doMerge}>Confirm</button> <button onClick={()=>{setMergeFrom(undefined); setMergeInto(undefined);}}>Cancel</button>
    </div>}
  </div>;
};

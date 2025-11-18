import React, { useState } from 'react';
import { uploadVideo, VideoMeta } from '../hooks/api';

interface Props { onUploaded:(v:VideoMeta)=>void }

export const VideoUpload:React.FC<Props> = ({ onUploaded }) => {
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState<string|undefined>();
  return <div style={{padding:'6px', borderBottom:'1px solid #222'}}>
    <input type="file" onChange={async e=>{
      if(!e.target.files?.length) return; setLoading(true); setError(undefined);
      try { const meta = await uploadVideo(e.target.files[0]); onUploaded(meta); } catch(err:any){ setError(err.message);} finally { setLoading(false);} }} />
    {loading && <span style={{marginLeft:8}}>Uploading...</span>}
    {error && <span style={{marginLeft:8, color:'#e57373'}}>{error}</span>}
  </div>;
};

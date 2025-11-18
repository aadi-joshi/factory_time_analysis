import React from 'react';
import { PersonSummary } from '../hooks/api';

export const SummaryTable:React.FC<{persons:PersonSummary[]; onExport:()=>void}> = ({ persons, onExport }) => {
  return <div style={{padding:'8px'}}>
    <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
      <h3 style={{fontSize:12, margin:0}}>Summary</h3>
      <button onClick={onExport}>Export CSV</button>
    </div>
    <table style={{width:'100%', fontSize:12, marginTop:6}}>
      <thead>
        <tr style={{textAlign:'left'}}>
          <th>ID</th><th>Name</th><th>Total(s)</th><th>VA(s)</th><th>NVA(s)</th><th>VA%</th>
        </tr>
      </thead>
      <tbody>
        {persons.map(p=> <tr key={p.person_id}>
          <td>{p.internal_track_id}</td>
          <td>{p.name}</td>
          <td>{p.total_time_seconds.toFixed(1)}</td>
          <td className="labelVA">{p.value_added_seconds.toFixed(1)}</td>
          <td className="labelNVA">{p.non_value_added_seconds.toFixed(1)}</td>
          <td>{(p.value_added_ratio*100).toFixed(1)}%</td>
        </tr>)}
      </tbody>
    </table>
  </div>;
};

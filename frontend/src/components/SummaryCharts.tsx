import React, { useEffect, useState } from 'react';
import { fetchAnalytics } from '../hooks/api';
import { Pie, Bar } from 'react-chartjs-2';
import { Chart, ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';
Chart.register(ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

interface Props { videoId:number; }

export const SummaryCharts:React.FC<Props> = ({ videoId }) => {
  const [data,setData] = useState<any|null>(null);
  useEffect(()=>{ (async()=>{ try { const a = await fetchAnalytics(videoId); setData(a); } catch(e){ /* ignore */ } })(); },[videoId]);
  if(!data) return <div style={{fontSize:12}}>Loading analytics...</div>;
  const totalVA = data.overall.value_added_seconds;
  const totalNVA = data.overall.non_value_added_seconds;
  const pieData = {
    labels:['Value-Added','Non-Value-Added'],
    datasets:[{ data:[totalVA, totalNVA], backgroundColor:['#00e676','#ff5252'] }]
  };
  const barData = {
    labels: data.persons.map((p:any)=> p.name),
    datasets:[
      { label:'VA (s)', backgroundColor:'#00e676', data: data.persons.map((p:any)=> p.value_added_seconds) },
      { label:'NVA (s)', backgroundColor:'#ff5252', data: data.persons.map((p:any)=> p.non_value_added_seconds) }
    ]
  };
  return <div style={{display:'flex', flexDirection:'column', gap:16}}>
    <div style={{display:'flex', gap:24, flexWrap:'wrap'}}>
      <div style={{width:260}}><h4 style={{margin:'4px 0', fontSize:12}}>Overall VA vs NVA</h4><Pie data={pieData} /></div>
      <div style={{flex:1, minWidth:360}}><h4 style={{margin:'4px 0', fontSize:12}}>Per-Person VA/NVA</h4><Bar data={barData} options={{responsive:true, plugins:{legend:{labels:{color:'#ddd'}}}, scales:{x:{ticks:{color:'#ddd'}}, y:{ticks:{color:'#ddd'}}}}} /></div>
    </div>
  </div>;
};

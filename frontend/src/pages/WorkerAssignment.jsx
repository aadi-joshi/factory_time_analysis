import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { videosApi, workerZonesApi, zonesApi, mergesApi, workersApi } from '../services/api';
import './WorkerAssignment.css';

function WorkerAssignment({ videoId: propVideoId }) {
    const params = useParams();
    const videoId = propVideoId || params.videoId;

    const [workers, setWorkers] = useState([]);
    const [zones, setZones] = useState([]);
    const [workerZones, setWorkerZones] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [processing, setProcessing] = useState(false);
    const [status, setStatus] = useState('');
    const [mergeMap, setMergeMap] = useState({});

    // ---------------- LOAD DATA ----------------
    const loadData = async () => {
        if (!videoId) return;

        try {
            setLoading(true);
            const [summaryRes, zonesRes, mappingsRes, mergesRes] = await Promise.all([
                videosApi.getSummary(videoId),
                zonesApi.getByVideo(videoId),
                workerZonesApi.getByVideo(videoId),
                mergesApi.getByVideo(videoId),
            ]);

            // Build merge map: original worker_id -> merged_worker_id
            const merges = mergesRes.data.merges || [];
            const mergeMapTemp = {};
            merges.forEach(m => {
                (m.original_track_ids || []).forEach(id => {
                    mergeMapTemp[String(id)] = m.merged_worker_id;
                });
            });
            setMergeMap(mergeMapTemp);

            // Only show unique merged workers
            const allWorkers = summaryRes.data.workers || [];
            // Get set of merged_worker_ids
            const mergedWorkerIds = new Set(Object.values(mergeMapTemp));
            // Filter: only show workers whose worker_id is not in mergeMapTemp (not merged away), or is a merged_worker_id
            const uniqueWorkers = allWorkers.filter(w => {
                // If this worker_id is an original id that was merged, skip it
                if (mergeMapTemp[w.worker_id] && mergeMapTemp[w.worker_id] !== w.worker_id) return false;
                // If this worker_id is a merged_worker_id, show it
                if (mergedWorkerIds.has(w.worker_id)) return true;
                // If this worker_id is not in mergeMapTemp at all, show it
                if (!mergeMapTemp[w.worker_id]) return true;
                return false;
            });
            setWorkers(uniqueWorkers);
            setZones(zonesRes.data.zones || []);

            const wz = {};
            mappingsRes.data.worker_zones?.forEach(w => {
                wz[w.worker_id] = w.va_zones || [];
            });
            setWorkerZones(wz);
        } catch {
            setError('Failed to load project data.');
        } finally {
            setLoading(false);
        }
    };

    // ---------------- INITIAL LOAD ----------------
    useEffect(() => {
        if (!videoId) {
            setError('No video selected.');
            setLoading(false);
            return;
        }
        loadData();
    }, [videoId]);

    // ---------------- STATUS POLLING (IMPORTANT FIX) ----------------
    useEffect(() => {
        if (!videoId) return;

        const interval = setInterval(async () => {
            try {
                const res = await videosApi.get(videoId);
                setStatus(res.data.status || '');
            } catch {
                setStatus('failed');
            }
        }, 3000);

        return () => clearInterval(interval);
    }, [videoId]);

    // ---------------- PROCESS VIDEO ----------------
    const handleProcess = async () => {
        try {
            setProcessing(true);
            await videosApi.process(videoId);
            setStatus('processing');
        } catch {
            setStatus('failed');
        } finally {
            setProcessing(false);
        }
    };

    // ---------------- TOGGLE ZONE ----------------
    const toggleZoneAssignment = async (workerId, zoneId) => {
        const vaZones = workerZones[workerId] || [];
        const isAssigned = vaZones.includes(zoneId);

        if (!isAssigned) {
            await workerZonesApi.assign({
                video_id: videoId,
                worker_id: workerId,
                zone_id: zoneId,
                is_va: true
            });
        }

        setWorkerZones(prev => ({
            ...prev,
            [workerId]: isAssigned
                ? prev[workerId].filter(z => z !== zoneId)
                : [...(prev[workerId] || []), zoneId]
        }));
    };

    const getWorkerDisplayName = (workerId) => {
        const merged = mergeMap[workerId];
        if (merged && merged !== workerId) {
            return `${merged} (orig ${workerId})`;
        }
        return workerId;
    };

    // ---------------- UI STATES ----------------
    if (loading) return <div style={{ padding: 32 }}>Loading...</div>;
    if (error) return <div style={{ padding: 32, color: 'red' }}>{error}</div>;

    if (status === 'failed') {
        return <div style={{ padding: 32, color: 'red' }}>Processing failed.</div>;
    }

    return (
        <div className="worker-assignment">
            <div className="container">
                <h2>Assign Zones to Workers</h2>

                <div style={{ marginBottom: 16 }}>
                    <b>Status:</b> {status}
                    {status !== 'complete' && (
                        <button
                            className="btn btn-primary"
                            style={{ marginLeft: 12 }}
                            onClick={handleProcess}
                            disabled={processing || status === 'processing'}
                        >
                            {processing || status === 'processing'
                                ? 'Processing...'
                                : 'Process Video'}
                        </button>
                    )}
                </div>

                {workers.length > 0 && (
                    <table>
                        <thead>
                            <tr>
                                <th>Preview</th>
                                <th>Merged Worker ID</th>
                                <th>Worker</th>
                                {zones.map(z => (
                                    <th key={z.id}>
                                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                            <span>{z.label}</span>
                                            {z.color && (
                                                <span style={{ display: 'inline-block', width: 24, height: 24, background: z.color, borderRadius: 4, border: '1px solid #888', marginTop: 2 }} title={z.color}></span>
                                            )}
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {workers.map(w => (
                                <tr key={w.worker_id}>
                                    <td>
                                        {w.merged_from && w.merged_from.length > 0 ? (
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, width: 96, minHeight: 48 }}>
                                                {w.merged_from.map(origId => (
                                                    <img
                                                        key={origId}
                                                        src={workersApi.getImageUrl(videoId, origId)}
                                                        alt={`Orig ${origId}`}
                                                        style={{ width: 44, height: 44, objectFit: 'contain', borderRadius: 6, border: '1.5px solid #888', background: '#f8f8f8' }}
                                                        onError={e => { e.target.onerror = null; e.target.src = 'https://via.placeholder.com/44?text=No+Image'; }}
                                                    />
                                                ))}
                                                {w.merged_from.length === 0 && (
                                                    <span style={{ fontSize: 12, color: '#888' }}>No Preview</span>
                                                )}
                                            </div>
                                        ) : (
                                            <img
                                                src={workersApi.getImageUrl(videoId, w.worker_id)}
                                                alt="Worker Preview"
                                                style={{ width: 96, height: 96, objectFit: 'contain', borderRadius: 8, border: '2px solid #333', background: '#fff' }}
                                                onError={e => { e.target.onerror = null; e.target.src = 'https://via.placeholder.com/96?text=No+Image'; }}
                                            />
                                        )}
                                    </td>
                                    <td style={{ fontWeight: 'bold', color: '#2a4d8f', fontSize: 18 }}>
                                        {w.merged_from && w.merged_from.length > 0 ? (
                                            <>
                                                {w.worker_id}
                                                <span style={{
                                                    background: '#f59e42',
                                                    color: '#fff',
                                                    borderRadius: 4,
                                                    padding: '2px 6px',
                                                    fontSize: 11,
                                                    marginLeft: 6,
                                                    fontWeight: 700,
                                                }}
                                                    title={`Merged from: ${w.merged_from.join(', ')}`}
                                                >
                                                    merged
                                                </span>
                                            </>
                                        ) : w.worker_id}
                                    </td>
                                    <td>
                                        {w.merged_from && w.merged_from.length > 0 ? (
                                            <span title={`Original IDs: ${w.merged_from.join(', ')}`}>Merged from: {w.merged_from.join(', ')}</span>
                                        ) : ''}
                                    </td>
                                    {zones.map(z => (
                                        <td key={z.id}>
                                            <input
                                                type="checkbox"
                                                checked={(workerZones[w.worker_id] || []).includes(z.id)}
                                                onChange={() =>
                                                    toggleZoneAssignment(w.worker_id, z.id)
                                                }
                                            />
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}

export default WorkerAssignment;

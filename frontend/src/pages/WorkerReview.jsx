import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { workersApi, mergesApi, analyticsApi } from '../services/api';
import './WorkerAssignment.css';

function WorkerReview({ videoId: propVideoId, onReviewComplete }) {
    const params = useParams();
    const videoId = propVideoId || params.videoId;

    const [workers, setWorkers] = useState([]);
    const [selected, setSelected] = useState([]);
    const [merging, setMerging] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [previewWorkerId, setPreviewWorkerId] = useState(null);
    const [reviewConfirmed, setReviewConfirmed] = useState(false);

    const loadWorkers = async () => {
        if (!videoId) return;
        try {
            setLoading(true);
            const res = await workersApi.list(videoId);
            setWorkers(res.data.workers || []);
        } catch (e) {
            console.error('Failed to load workers', e);
            setError('Failed to load detected workers.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!videoId) {
            setError('No video selected.');
            setLoading(false);
            return;
        }
        loadWorkers();
    }, [videoId]);

    const toggleSelect = (workerId) => {
        setSelected((prev) =>
            prev.includes(workerId) ? prev.filter((id) => id !== workerId) : [...prev, workerId]
        );
        // Always update the preview focus to the last clicked worker
        setPreviewWorkerId(workerId);
    };

    const handleMerge = async () => {
        if (selected.length < 2) {
            alert('Select at least two workers to merge.');
            return;
        }

        const mergedWorkerId = prompt(
            'Enter a unified worker ID for the merged person (e.g., 1 or A):',
            selected[0]
        );
        if (!mergedWorkerId) return;

        setMerging(true);
        setStatusMessage('Saving merge and recomputing metrics...');

        try {
            await mergesApi.create({
                video_id: videoId,
                merged_worker_id: String(mergedWorkerId),
                original_track_ids: selected.map((id) => parseInt(id, 10)).filter((n) => !Number.isNaN(n)),
                notes: 'Merged via WorkerReview UI',
            });

            // Recompute metrics so analytics reflect the merge
            await analyticsApi.computeMetrics(videoId);

            setSelected([]);
            setStatusMessage('Merge saved and metrics recomputed.');
            loadWorkers();
        } catch (e) {
            console.error('Failed to merge workers', e);
            setStatusMessage('Failed to merge workers.');
        } finally {
            setMerging(false);
        }
    };

    if (loading) return <div style={{ padding: 32 }}>Loading detected workers...</div>;
    if (error) return <div style={{ padding: 32, color: 'red' }}>{error}</div>;
    if (reviewConfirmed) {
        if (onReviewComplete) onReviewComplete();
        return <div style={{ padding: 32, color: '#166534' }}>All detected workers reviewed and confirmed! You may now proceed to zone assignment.</div>;
    }

    return (
        <div className="worker-assignment">
            <div className="container">
                <h2>Review Detected Workers</h2>
                <p style={{ marginBottom: 12 }}>
                    Below are all detected people for this video. Select multiple entries that represent
                    the same real person and click <b>Merge Selected</b> to unify them for analytics.
                </p>

                {statusMessage && (
                    <div style={{ marginBottom: 12, color: merging ? '#92400e' : '#166534' }}>
                        {statusMessage}
                    </div>
                )}

                {workers.length === 0 ? (
                    <p>No workers detected yet. Make sure processing has completed.</p>
                ) : (
                    <>
                        <button
                            className="btn btn-primary"
                            style={{ marginBottom: 16, marginRight: 12 }}
                            onClick={handleMerge}
                            disabled={merging || selected.length < 2}
                        >
                            {merging ? 'Merging...' : `Merge Selected (${selected.length})`}
                        </button>
                        <button
                            className="btn btn-success"
                            style={{ marginBottom: 16 }}
                            onClick={() => setReviewConfirmed(true)}
                            disabled={merging || workers.length === 0}
                        >
                            Confirm All
                        </button>

                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '2fr 3fr',
                                gap: '24px',
                                alignItems: 'flex-start',
                            }}
                        >
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                                    gap: '16px',
                                }}
                            >
                                {workers.map((w) => {
                                    const isMerged = !!w.merged_from;
                                    return (
                                        <div
                                            key={w.worker_id}
                                            className="worker-card"
                                            style={{
                                                border: selected.includes(w.worker_id)
                                                    ? '2.5px solid #2563eb'
                                                    : isMerged
                                                        ? '2px solid #f59e42'
                                                        : '1px solid #e5e7eb',
                                                borderRadius: 8,
                                                padding: 12,
                                                cursor: 'pointer',
                                                backgroundColor: selected.includes(w.worker_id)
                                                    ? '#eff6ff'
                                                    : isMerged
                                                        ? '#fff7ed'
                                                        : 'white',
                                                boxShadow: isMerged ? '0 0 0 2px #f59e42' : undefined,
                                            }}
                                            onClick={() => toggleSelect(w.worker_id)}
                                            title={isMerged ? `Merged from: ${w.merged_from.join(', ')}` : ''}
                                        >
                                            {/* Only show labels, no image preview */}
                                            <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                                                Worker {w.worker_id}
                                                {isMerged && (
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
                                                )}
                                            </div>
                                            {isMerged && (
                                                <div style={{ fontSize: 12, color: '#b45309', marginBottom: 2 }}>
                                                    <span title={`Original IDs: ${w.merged_from.join(', ')}`}>Merged from: {w.merged_from.join(', ')}</span>
                                                </div>
                                            )}
                                            <div style={{ fontSize: 12, color: '#6b7280' }}>
                                                Frames: {w.total_frames} (from {w.first_frame} to {w.last_frame})
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            <div
                                style={{
                                    border: '1px solid #e5e7eb',
                                    borderRadius: 8,
                                    padding: 16,
                                    minHeight: 260,
                                    backgroundColor: '#f9fafb',
                                }}
                            >
                                <h3 style={{ marginTop: 0, marginBottom: 8 }}>Person preview</h3>
                                <p style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
                                    Click on a card on the left to see the first
                                    frame where that person was detected, with a
                                    colored box around them. This helps verify you
                                    are merging the correct real person.
                                </p>
                                {previewWorkerId ? (
                                    <div>
                                        <div
                                            style={{
                                                fontSize: 13,
                                                fontWeight: 600,
                                                marginBottom: 8,
                                            }}
                                        >
                                            Worker {previewWorkerId}
                                        </div>
                                        <img
                                            src={
                                                workersApi.getFirstDetectionFrameUrl(
                                                    videoId,
                                                    previewWorkerId
                                                )
                                            }
                                            alt={`First detection for worker ${previewWorkerId}`}
                                            style={{
                                                width: '100%',
                                                maxHeight: 320,
                                                objectFit: 'contain',
                                                borderRadius: 6,
                                                border: '1px solid #d1d5db',
                                                backgroundColor: 'black',
                                            }}
                                        />
                                    </div>
                                ) : (
                                    <div
                                        style={{
                                            height: 220,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            color: '#9ca3af',
                                            fontSize: 13,
                                            borderRadius: 6,
                                            border: '1px dashed #d1d5db',
                                            backgroundColor: 'white',
                                        }}
                                    >
                                        No person selected yet.
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default WorkerReview;

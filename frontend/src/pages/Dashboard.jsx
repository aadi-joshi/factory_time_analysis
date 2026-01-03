import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './Dashboard.css'

function Dashboard({ videos, onVideoSelected, loading }) {
    const formatDate = (dateString) => {
        const date = new Date(dateString)
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
    }

    const getStatusColor = (status) => {
        switch (status) {
            case 'complete':
                return '#10b981'
            case 'processing':
                return '#f59e0b'
            case 'failed':
                return '#ef4444'
            default:
                return '#6b7280'
        }
    }
    const navigate = useNavigate()

    const handleDelete = async (videoId) => {
        if (!window.confirm('Are you sure you want to delete this project and all its data?')) return;
        try {
            const { videosApi } = await import('../services/api');
            await videosApi.delete(videoId);
            // Remove from UI without reload
            if (typeof window !== 'undefined') {
                window.location.reload();
            }
        } catch (err) {
            alert('Failed to delete project. Please ensure the backend supports DELETE /api/videos/{video_id}');
        }
    };

    return (
        <div className="dashboard">
            <div className="container">
                <div className="dashboard-header">
                    <h2>Videos & Projects</h2>
                    <Link to="/upload" className="btn btn-primary">
                        Upload New Video
                    </Link>
                </div>

                {loading ? (
                    <div className="loading">Loading videos...</div>
                ) : videos.length === 0 ? (
                    <div className="empty-state">
                        <p>No videos yet. Start by uploading a video.</p>
                        <Link to="/upload" className="btn btn-primary">
                            Upload Video
                        </Link>
                    </div>
                ) : (
                    <div className="videos-grid">
                        {videos.map((video) => (
                            <div key={video.id} className="video-card">
                                <div className="video-header">
                                    <h3>{video.filename}</h3>
                                    <span
                                        className="status-badge"
                                        style={{ backgroundColor: getStatusColor(video.status) }}
                                    >
                                        {video.status}
                                    </span>
                                </div>

                                <div className="video-info">
                                    <p><strong>Duration:</strong> {video.duration_sec?.toFixed(1)}s</p>
                                    <p><strong>Uploaded:</strong> {formatDate(video.uploaded_at)}</p>
                                </div>

                                <div className="video-actions">
                                    <Link
                                        to={`/zones/${video.id}`}
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => onVideoSelected(video.id)}
                                    >
                                        Define Zones
                                    </Link>
                                    <Link
                                        to={`/assignment/${video.id}`}
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => onVideoSelected(video.id)}
                                    >
                                        Assign Workers
                                    </Link>
                                    <button
                                        className="btn btn-link"
                                        onClick={() => navigate(`/workers/${video.id}`)}
                                    >
                                        Workers
                                    </button>
                                    <Link
                                        to={`/analytics/${video.id}`}
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => onVideoSelected(video.id)}
                                    >
                                        Analytics
                                    </Link>
                                    <button
                                        className="btn btn-danger btn-sm"
                                        style={{ marginLeft: 8 }}
                                        onClick={() => handleDelete(video.id)}
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}

export default Dashboard

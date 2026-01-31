import React, { useState, useEffect } from 'react'
import { ErrorBoundary } from 'react-error-boundary'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Dashboard from './pages/Dashboard'
import VideoUpload from './pages/VideoUpload'
import ZoneEditor from './pages/ZoneEditor'
import WorkerAssignment from './pages/WorkerAssignment'
import WorkerReview from './pages/WorkerReview'
import Analytics from './pages/Analytics'
import VideoClipper from './pages/VideoClipper'
import './App.css'

function ErrorFallback({ error }) {
    return (
        <div style={{ color: 'red', padding: 32 }}>
            <h2>Something went wrong</h2>
            <pre>{error?.message || String(error)}</pre>
        </div>
    );
}

function App() {
    const [videos, setVideos] = useState([])
    const [selectedVideo, setSelectedVideo] = useState(null)

    // Support direct navigation by extracting videoId from URL if needed
    const getVideoIdFromPath = () => {
        const match = window.location.pathname.match(/\/(zones|assignment|analytics|workers)\/(.+)/);
        return match ? match[2] : null;
    };

    useEffect(() => {
        if (!selectedVideo) {
            const vid = getVideoIdFromPath();
            if (vid) setSelectedVideo(vid);
        }
    }, [selectedVideo]);
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        loadVideos()
    }, [])

    const loadVideos = async () => {
        try {
            setLoading(true)
            const response = await fetch('/api/videos')
            const data = await response.json()
            setVideos(data.videos || [])
        } catch (error) {
            console.error('Error loading videos:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleVideoSelected = (videoId) => {
        setSelectedVideo(videoId)
    }

    const handleVideoUploaded = () => {
        loadVideos()
    }

    return (
        <ErrorBoundary FallbackComponent={ErrorFallback}>
            <Router>
                <div className="app">
                    <Header />
                    <main className="main-content">
                        <Routes>
                            <Route
                                path="/"
                                element={
                                    <Dashboard
                                        videos={videos}
                                        onVideoSelected={handleVideoSelected}
                                        loading={loading}
                                    />
                                }
                            />
                            <Route
                                path="/upload"
                                element={<VideoUpload onVideoUploaded={handleVideoUploaded} />}
                            />
                            <Route
                                path="/clipper"
                                element={<VideoClipper />}
                            />
                            <Route
                                path="/zones/:videoId"
                                element={<ZoneEditor videoId={selectedVideo} />}
                            />
                            <Route
                                path="/assignment/:videoId"
                                element={<WorkerAssignment videoId={selectedVideo} />}
                            />
                            <Route
                                path="/workers/:videoId"
                                element={<WorkerReview videoId={selectedVideo} />}
                            />
                            <Route
                                path="/analytics/:videoId"
                                element={<Analytics videoId={selectedVideo} />}
                            />
                        </Routes>
                    </main>
                </div>
            </Router>
        </ErrorBoundary>
    )
}

export default App

import React, { useState, useRef } from 'react'
import './VideoClipper.css'

function VideoClipper() {
    const [videoFile, setVideoFile] = useState(null)
    const [excelFile, setExcelFile] = useState(null)
    const [jobId, setJobId] = useState(null)
    const [jobStatus, setJobStatus] = useState(null)
    const [uploading, setUploading] = useState(false)
    const [error, setError] = useState(null)

    const videoInputRef = useRef(null)
    const excelInputRef = useRef(null)
    const pollIntervalRef = useRef(null)

    const handleVideoChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            setVideoFile(file)
            setError(null)
        }
    }

    const handleExcelChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            setExcelFile(file)
            setError(null)
        }
    }

    const handleSubmit = async () => {
        if (!videoFile || !excelFile) {
            setError('Please select both video and Excel files')
            return
        }

        setUploading(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('video', videoFile)
            formData.append('excel', excelFile)

            const response = await fetch('/api/video-clipper/upload', {
                method: 'POST',
                body: formData
            })

            if (!response.ok) {
                const errorData = await response.json()
                throw new Error(errorData.detail || 'Upload failed')
            }

            const data = await response.json()
            setJobId(data.job_id)

            // Start polling for job status
            startPolling(data.job_id)
        } catch (err) {
            setError(err.message)
            setUploading(false)
        }
    }

    const startPolling = (id) => {
        // Clear any existing interval
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
        }

        // Poll every 2 seconds
        pollIntervalRef.current = setInterval(async () => {
            try {
                const response = await fetch(`/api/video-clipper/jobs/${id}`)
                if (!response.ok) {
                    throw new Error('Failed to fetch job status')
                }

                const data = await response.json()
                setJobStatus(data)

                // Stop polling if job is complete or failed
                if (data.status === 'complete' || data.status === 'failed') {
                    clearInterval(pollIntervalRef.current)
                    setUploading(false)
                }
            } catch (err) {
                console.error('Error polling job status:', err)
            }
        }, 2000)
    }

    const handleReset = () => {
        setVideoFile(null)
        setExcelFile(null)
        setJobId(null)
        setJobStatus(null)
        setError(null)
        setUploading(false)

        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
        }

        if (videoInputRef.current) videoInputRef.current.value = ''
        if (excelInputRef.current) excelInputRef.current.value = ''
    }

    // Group clips by folder
    const groupedClips = jobStatus?.clips?.reduce((acc, clip) => {
        if (!acc[clip.folder]) {
            acc[clip.folder] = []
        }
        acc[clip.folder].push(clip)
        return acc
    }, {}) || {}

    return (
        <div className="video-clipper">
            <div className="clipper-header">
                <h1>Video Clipper</h1>
                <p>Upload a video and Excel file with timestamps to automatically generate clips</p>
            </div>

            {!jobId ? (
                <div className="upload-section">
                    <div className="file-upload-group">
                        <div className="file-upload-item">
                            <label htmlFor="video-upload" className="upload-label">
                                <span className="label-text">Video File</span>
                                <span className="file-info">
                                    {videoFile ? videoFile.name : 'No file selected'}
                                </span>
                            </label>
                            <input
                                ref={videoInputRef}
                                id="video-upload"
                                type="file"
                                accept="video/*"
                                onChange={handleVideoChange}
                                className="file-input"
                            />
                            <button
                                onClick={() => videoInputRef.current?.click()}
                                className="select-file-btn"
                            >
                                {videoFile ? 'Change Video' : 'Select Video'}
                            </button>
                        </div>

                        <div className="file-upload-item">
                            <label htmlFor="excel-upload" className="upload-label">
                                <span className="label-text">Excel Timestamps</span>
                                <span className="file-info">
                                    {excelFile ? excelFile.name : 'No file selected'}
                                </span>
                            </label>
                            <input
                                ref={excelInputRef}
                                id="excel-upload"
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={handleExcelChange}
                                className="file-input"
                            />
                            <button
                                onClick={() => excelInputRef.current?.click()}
                                className="select-file-btn"
                            >
                                {excelFile ? 'Change Excel' : 'Select Excel'}
                            </button>
                        </div>
                    </div>

                    {error && (
                        <div className="error-message">
                            {error}
                        </div>
                    )}

                    <button
                        onClick={handleSubmit}
                        disabled={!videoFile || !excelFile || uploading}
                        className="submit-btn"
                    >
                        {uploading ? 'Processing...' : 'Start Clipping'}
                    </button>

                    <div className="info-box">
                        <h3>Excel Format Requirements:</h3>
                        <ul>
                            <li><strong>start_time</strong>: Start time of clip (HH:MM:SS or MM:SS)</li>
                            <li><strong>end_time</strong>: End time of clip (HH:MM:SS or MM:SS)</li>
                            <li><strong>action_name</strong>: Name of the action</li>
                            <li><strong>VA_RNVA_NVA</strong>: Classification (optional)</li>
                        </ul>
                    </div>
                </div>
            ) : (
                <div className="job-status-section">
                    <div className="status-header">
                        <h2>Job Status</h2>
                        <span className={`status-badge status-${jobStatus?.status}`}>
                            {jobStatus?.status || 'pending'}
                        </span>
                    </div>

                    {jobStatus?.status === 'processing' && (
                        <div className="progress-section">
                            <div className="progress-bar">
                                <div
                                    className="progress-fill"
                                    style={{ width: `${jobStatus.progress || 0}%` }}
                                />
                            </div>
                            <p className="progress-text">
                                {jobStatus.progress}% - Processing clip {jobStatus.processed_clips} of {jobStatus.total_clips}
                            </p>
                        </div>
                    )}

                    {jobStatus?.status === 'failed' && (
                        <div className="error-message">
                            Error: {jobStatus.error_message}
                        </div>
                    )}

                    {jobStatus?.status === 'complete' && jobStatus.clips && (
                        <div className="clips-section">
                            <div className="clips-header">
                                <h3>Generated Clips ({jobStatus.total_clips})</h3>
                                <button onClick={handleReset} className="reset-btn">
                                    Create New Job
                                </button>
                            </div>

                            {Object.keys(groupedClips).map(folder => (
                                <div key={folder} className="clip-folder">
                                    <h4 className="folder-name">{folder}</h4>
                                    <div className="clips-grid">
                                        {groupedClips[folder].map((clip, idx) => (
                                            <div key={idx} className="clip-card">
                                                <div className="clip-info">
                                                    <span className="clip-filename">{clip.filename}</span>
                                                    <span className="clip-duration">
                                                        {clip.duration_sec.toFixed(2)}s
                                                    </span>
                                                </div>
                                                <a
                                                    href={clip.download_url}
                                                    download={clip.filename}
                                                    className="download-btn"
                                                >
                                                    Download
                                                </a>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {jobStatus?.status === 'pending' && (
                        <div className="loading-message">
                            <div className="spinner"></div>
                            <p>Initializing job...</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default VideoClipper

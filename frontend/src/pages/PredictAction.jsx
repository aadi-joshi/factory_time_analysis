import React, { useState, useRef } from 'react'
import axios from 'axios'
import './PredictAction.css'

function PredictAction() {
    const [selectedFile, setSelectedFile] = useState(null)
    const [jobId, setJobId] = useState(null)
    const [status, setStatus] = useState(null)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)
    const [uploading, setUploading] = useState(false)
    const [processing, setProcessing] = useState(false)
    const fileInputRef = useRef(null)

    const handleFileSelect = (e) => {
        const file = e.target.files[0]
        if (file) {
            setSelectedFile(file)
            setError(null)
        }
    }

    const handleDrop = (e) => {
        e.preventDefault()
        const file = e.dataTransfer.files[0]
        if (file && file.type.startsWith('video/')) {
            setSelectedFile(file)
            setError(null)
        } else {
            setError('Please drop a valid video file')
        }
    }

    const handleDragOver = (e) => {
        e.preventDefault()
    }

    const handleUpload = async () => {
        if (!selectedFile) {
            setError('Please select a video file')
            return
        }

        setUploading(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('video', selectedFile)

            const response = await axios.post('/api/predict-action/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            })

            setJobId(response.data.job_id)

            // Automatically start processing
            await startProcessing(response.data.job_id)
        } catch (err) {
            setError(err.response?.data?.detail || 'Upload failed')
        } finally {
            setUploading(false)
        }
    }

    const startProcessing = async (id) => {
        setProcessing(true)
        setError(null)

        try {
            await axios.post(`/api/predict-action/${id}/process`)

            // Poll for status
            pollStatus(id)
        } catch (err) {
            setError(err.response?.data?.detail || 'Processing failed')
            setProcessing(false)
        }
    }

    const pollStatus = async (id) => {
        const interval = setInterval(async () => {
            try {
                const statusResponse = await axios.get(`/api/predict-action/${id}/status`)
                setStatus(statusResponse.data)

                if (statusResponse.data.status === 'complete') {
                    clearInterval(interval)
                    setProcessing(false)

                    // Fetch full results
                    const resultResponse = await axios.get(`/api/predict-action/${id}/result`)
                    setResult(resultResponse.data)
                } else if (statusResponse.data.status === 'failed') {
                    clearInterval(interval)
                    setProcessing(false)
                    setError(statusResponse.data.message || 'Prediction failed')
                }
            } catch (err) {
                clearInterval(interval)
                setProcessing(false)
                setError('Failed to get status')
            }
        }, 2000) // Poll every 2 seconds
    }

    const handleReset = () => {
        setSelectedFile(null)
        setJobId(null)
        setStatus(null)
        setResult(null)
        setError(null)
        setUploading(false)
        setProcessing(false)
        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const getValueCategoryColor = (category) => {
        switch (category) {
            case 'VA':
                return '#00ff00' // Green
            case 'RNVA':
                return '#ff8c00' // Orange
            case 'NVA':
                return '#ff0000' // Red
            default:
                return '#808080' // Gray
        }
    }

    const getValueCategoryLabel = (category) => {
        switch (category) {
            case 'VA':
                return 'Value Added'
            case 'RNVA':
                return 'Required Non-Value Added'
            case 'NVA':
                return 'Non-Value Added'
            default:
                return 'Unknown'
        }
    }

    return (
        <div className="predict-action-container">
            <div className="predict-action-header">
                <h1>Predict Action</h1>
                <p>Upload a factory video to predict assembly actions using AI</p>
            </div>

            {/* Upload Section */}
            {!jobId && (
                <div className="upload-section">
                    <div
                        className="drop-zone"
                        onDrop={handleDrop}
                        onDragOver={handleDragOver}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="video/*"
                            onChange={handleFileSelect}
                            style={{ display: 'none' }}
                        />
                        {selectedFile ? (
                            <div className="file-selected">
                                <span className="file-icon">🎬</span>
                                <p className="file-name">{selectedFile.name}</p>
                                <p className="file-size">
                                    {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                                </p>
                            </div>
                        ) : (
                            <div className="drop-zone-content">
                                <span className="upload-icon">📤</span>
                                <p>Drag and drop a video file here</p>
                                <p className="or-text">or</p>
                                <button className="browse-button">Browse Files</button>
                                <p className="supported-formats">Supported: MP4, AVI, MOV, MKV</p>
                            </div>
                        )}
                    </div>

                    {error && <div className="error-message">{error}</div>}

                    {selectedFile && (
                        <div className="upload-actions">
                            <button
                                className="upload-button"
                                onClick={handleUpload}
                                disabled={uploading}
                            >
                                {uploading ? 'Uploading...' : 'Upload & Predict'}
                            </button>
                            <button className="cancel-button" onClick={handleReset}>
                                Cancel
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Processing Status */}
            {processing && status && (
                <div className="processing-section">
                    <h2>Processing Video...</h2>
                    <div className="progress-bar">
                        <div
                            className="progress-fill"
                            style={{ width: `${status.progress || 0}%` }}
                        ></div>
                    </div>
                    <p className="progress-text">{status.progress || 0}% Complete</p>
                    <p className="status-text">Status: {status.status}</p>
                </div>
            )}

            {/* Results Section */}
            {result && result.status === 'complete' && result.result && (
                <div className="results-section">
                    <div className="results-header">
                        <h2>Prediction Results</h2>
                        <button className="new-prediction-button" onClick={handleReset}>
                            New Prediction
                        </button>
                    </div>

                    <div className="prediction-cards">
                        <div className="prediction-card">
                            <h3>Coarse Action</h3>
                            <p className="action-value">{result.result.coarse_action}</p>
                        </div>

                        <div className="prediction-card">
                            <h3>Fine Action</h3>
                            <p className="action-value">{result.result.fine_action}</p>
                        </div>

                        <div className="prediction-card">
                            <h3>Value Category</h3>
                            <div
                                className="value-badge"
                                style={{
                                    backgroundColor: getValueCategoryColor(
                                        result.result.value_category
                                    ),
                                }}
                            >
                                {result.result.value_category}
                            </div>
                            <p className="value-description">
                                {getValueCategoryLabel(result.result.value_category)}
                            </p>
                        </div>

                        <div className="prediction-card">
                            <h3>Video Info</h3>
                            <p>Duration: {result.result.duration.toFixed(2)}s</p>
                            <p>FPS: {result.result.fps.toFixed(1)}</p>
                        </div>
                    </div>

                    {/* Video Player */}
                    <div className="video-player-section">
                        <h3>Annotated Video</h3>
                        <video
                            key={jobId}
                            className="annotated-video"
                            controls
                            preload="metadata"
                            onError={(e) => {
                                console.error('Video playback error:', e)
                                console.error('Video src:', e.target.src)
                            }}
                        >
                            <source src={`/api/predict-action/${jobId}/video`} type="video/webm" />
                            <source src={`/api/predict-action/${jobId}/video`} type="video/mp4" />
                            Your browser does not support the video tag.
                        </video>
                        <a
                            href={`/api/predict-action/${jobId}/video`}
                            download={`predicted_${result.filename}`}
                            className="download-button"
                        >
                            Download Annotated Video
                        </a>
                    </div>
                </div>
            )}

            {/* Error Display */}
            {result && result.status === 'failed' && (
                <div className="error-section">
                    <h2>Prediction Failed</h2>
                    <p className="error-message">{result.error || 'Unknown error occurred'}</p>
                    <button className="retry-button" onClick={handleReset}>
                        Try Again
                    </button>
                </div>
            )}
        </div>
    )
}

export default PredictAction

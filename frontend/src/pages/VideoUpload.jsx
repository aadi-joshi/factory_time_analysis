import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { videosApi } from '../services/api'
import './VideoUpload.css'

function VideoUpload({ onVideoUploaded }) {
    const [selectedFile, setSelectedFile] = useState(null)
    const [uploading, setUploading] = useState(false)
    const [error, setError] = useState(null)
    const [success, setSuccess] = useState(false)
    const navigate = useNavigate()

    const handleFileSelect = (e) => {
        const file = e.target.files[0]
        if (file) {
            if (!file.type.startsWith('video/')) {
                setError('Please select a valid video file')
                return
            }
            setSelectedFile(file)
            setError(null)
        }
    }

    const handleUpload = async (e) => {
        e.preventDefault()
        if (!selectedFile) {
            setError('Please select a file')
            return
        }

        try {
            setUploading(true)
            setError(null)
            const response = await videosApi.upload(selectedFile)
            setSuccess(true)
            onVideoUploaded()
            setTimeout(() => {
                navigate(`/zones/${response.data.id}`)
            }, 1000)
        } catch (err) {
            setError(err.response?.data?.detail || 'Upload failed. Please try again.')
        } finally {
            setUploading(false)
        }
    }

    return (
        <div className="upload-container">
            <div className="container" style={{ maxWidth: '600px' }}>
                <div className="upload-card">
                    <h2>Upload Video</h2>
                    <p>Upload a production line or factory video in MP4, AVI, or MOV format.</p>

                    <form onSubmit={handleUpload}>
                        <div className="upload-area">
                            <input
                                type="file"
                                accept="video/*"
                                onChange={handleFileSelect}
                                className="file-input"
                                disabled={uploading}
                            />
                            <div className="upload-prompt">
                                <p>📹 Select a video file</p>
                                <p style={{ fontSize: '0.9rem', color: 'var(--gray-500)' }}>
                                    Supported: MP4, AVI, MOV (max 4GB)
                                </p>
                            </div>
                            {selectedFile && (
                                <div className="selected-file">
                                    ✓ {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                                </div>
                            )}
                        </div>

                        {error && <div className="error-message">{error}</div>}
                        {success && <div className="success-message">✓ Video uploaded successfully!</div>}

                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={!selectedFile || uploading}
                            style={{ width: '100%', marginTop: '1rem' }}
                        >
                            {uploading ? 'Uploading...' : 'Upload Video'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    )
}

export default VideoUpload

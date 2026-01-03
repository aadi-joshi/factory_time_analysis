import React, { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { videosApi, zonesApi } from '../services/api'
import './ZoneEditor.css'

function ZoneEditor({ videoId: propVideoId }) {
    const params = useParams()
    const videoId = propVideoId || params.videoId
    const [firstFrame, setFirstFrame] = useState(null)
    const [zones, setZones] = useState([])
    const [newZoneName, setNewZoneName] = useState('')
    const [newZoneColor, setNewZoneColor] = useState('#FF5733')
    const [isDrawing, setIsDrawing] = useState(false)
    const [currentPolygon, setCurrentPolygon] = useState([])
    const canvasRef = useRef(null)

    useEffect(() => {
        if (videoId) {
            loadFirstFrame()
            loadZones()
        }
    }, [videoId])

    useEffect(() => {
        if (firstFrame) {
            redrawCanvas(firstFrame, zones)
        }
    }, [firstFrame, zones, currentPolygon])

    const loadFirstFrame = async () => {
        try {
            const frameUrl = videosApi.getFirstFrame(videoId)
            const img = new Image()
            img.crossOrigin = 'anonymous'
            img.onload = () => {
                setFirstFrame(img)
                const canvas = canvasRef.current
                if (canvas) {
                    canvas.width = img.width
                    canvas.height = img.height
                    redrawCanvas(img, zones)
                }
            }
            img.onerror = (err) => {
                console.error('Error loading frame image:', frameUrl, err)
            }
            img.src = frameUrl
        } catch (error) {
            console.error('Error loading frame:', error)
        }
    }

    const loadZones = async () => {
        try {
            const response = await zonesApi.getByVideo(videoId)
            setZones(response.data.zones || [])
        } catch (error) {
            console.error('Error loading zones:', error)
        }
    }

    const redrawCanvas = (img, zonesData) => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0)

        // Draw existing zones
        zonesData.forEach(zone => {
            ctx.strokeStyle = zone.color
            ctx.lineWidth = 2
            ctx.fillStyle = zone.color + '40'
            ctx.beginPath()
            zone.polygon.forEach((point, idx) => {
                if (idx === 0) ctx.moveTo(point[0], point[1])
                else ctx.lineTo(point[0], point[1])
            })
            ctx.closePath()
            ctx.fill()
            ctx.stroke()
        })

        // Draw current polygon
        if (currentPolygon.length > 0) {
            ctx.strokeStyle = newZoneColor
            ctx.lineWidth = 2
            ctx.fillStyle = newZoneColor + '40'
            ctx.beginPath()
            currentPolygon.forEach((point, idx) => {
                if (idx === 0) ctx.moveTo(point[0], point[1])
                else ctx.lineTo(point[0], point[1])
            })
            ctx.closePath()
            ctx.fill()
            ctx.stroke()

            // Draw points
            currentPolygon.forEach(point => {
                ctx.fillStyle = newZoneColor
                ctx.beginPath()
                ctx.arc(point[0], point[1], 5, 0, Math.PI * 2)
                ctx.fill()
            })
        }
    }

    const handleCanvasClick = (e) => {
        if (!isDrawing) return

        const canvas = canvasRef.current
        const rect = canvas.getBoundingClientRect()
        const x = e.clientX - rect.left
        const y = e.clientY - rect.top

        setCurrentPolygon([...currentPolygon, [x, y]])
    }

    const finishZone = async () => {
        if (currentPolygon.length < 3) {
            alert('A zone must have at least 3 points')
            return
        }

        if (!newZoneName.trim()) {
            alert('Please enter a zone name')
            return
        }

        try {
            await zonesApi.create({
                video_id: videoId,
                label: newZoneName,
                polygon: currentPolygon,
                color: newZoneColor
            })

            setCurrentPolygon([])
            setNewZoneName('')
            setIsDrawing(false)
            loadZones()
            redrawCanvas(firstFrame, zones)
        } catch (error) {
            console.error('Error creating zone:', error)
        }
    }

    return (
        <div className="zone-editor">
            <div className="container">
                <h2>Draw Zones on First Frame</h2>

                <div className="editor-layout">
                    <div className="canvas-area">
                        <canvas
                            ref={canvasRef}
                            onClick={handleCanvasClick}
                            className="zone-canvas"
                            style={{ cursor: isDrawing ? 'crosshair' : 'pointer' }}
                        />
                    </div>

                    <div className="controls-panel">
                        <div className="zone-form">
                            <h3>New Zone</h3>

                            <div className="form-group">
                                <label>Zone Name:</label>
                                <input
                                    type="text"
                                    value={newZoneName}
                                    onChange={(e) => setNewZoneName(e.target.value)}
                                    placeholder="e.g., Assembly"
                                    disabled={isDrawing}
                                />
                            </div>

                            <div className="form-group">
                                <label>Color:</label>
                                <input
                                    type="color"
                                    value={newZoneColor}
                                    onChange={(e) => setNewZoneColor(e.target.value)}
                                    disabled={isDrawing}
                                />
                            </div>

                            <div className="button-group">
                                {!isDrawing ? (
                                    <button className="btn btn-primary" onClick={() => setIsDrawing(true)}>
                                        Start Drawing
                                    </button>
                                ) : (
                                    <>
                                        <button className="btn btn-secondary" onClick={finishZone}>
                                            Save Zone ({currentPolygon.length} points)
                                        </button>
                                        <button
                                            className="btn btn-danger"
                                            onClick={() => {
                                                setCurrentPolygon([])
                                                setIsDrawing(false)
                                                redrawCanvas(firstFrame, zones)
                                            }}
                                        >
                                            Cancel
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>

                        <div className="zones-list">
                            <h3>Created Zones</h3>
                            {zones.length === 0 ? (
                                <p>No zones yet</p>
                            ) : (
                                zones.map((zone) => (
                                    <div key={zone.id} className="zone-item">
                                        <div
                                            className="zone-color"
                                            style={{ backgroundColor: zone.color }}
                                        />
                                        <span>{zone.label}</span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default ZoneEditor

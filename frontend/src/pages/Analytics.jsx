import React, { useState, useEffect } from 'react'
import { analyticsApi } from '../services/api'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import './Analytics.css'

function Analytics({ videoId }) {
    const [metrics, setMetrics] = useState([])
    const [loading, setLoading] = useState(true)
    const [computing, setComputing] = useState(false)

    useEffect(() => {
        if (videoId) {
            loadMetrics()
        }
    }, [videoId])

    const loadMetrics = async () => {
        try {
            setLoading(true)
            const response = await analyticsApi.getMetrics(videoId)
            setMetrics(response.data.metrics || [])
        } catch (error) {
            console.error('Error loading metrics:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleCompute = async () => {
        if (!videoId) return
        try {
            setComputing(true)
            await analyticsApi.computeMetrics(videoId)
            await loadMetrics()
        } catch (error) {
            console.error('Error computing metrics:', error)
        } finally {
            setComputing(false)
        }
    }

    if (loading) {
        return <div className="container" style={{ padding: '2rem' }}>Loading metrics...</div>
    }

    if (metrics.length === 0) {
        return (
            <div className="container" style={{ padding: '2rem', textAlign: 'center' }}>
                <p>No metrics available yet. After assigning VA zones and reviewing workers, compute metrics.</p>
                <button
                    className="btn btn-primary"
                    style={{ marginTop: '1rem' }}
                    onClick={handleCompute}
                    disabled={computing}
                >
                    {computing ? 'Computing...' : 'Compute Metrics'}
                </button>
            </div>
        )
    }

    const totalVASeconds = metrics.reduce((sum, m) => sum + m.va_seconds, 0)
    const totalNVASeconds = metrics.reduce((sum, m) => sum + m.nva_seconds, 0)
    const totalSeconds = totalVASeconds + totalNVASeconds

    const pieData = [
        { name: 'VA Time', value: totalVASeconds },
        { name: 'NVA Time', value: totalNVASeconds }
    ]

    const COLORS = ['#10b981', '#ef4444']

    return (
        <div className="analytics">
            <div className="container">
                <h2>VA/NVA Analytics</h2>

                <div style={{ marginBottom: '1rem' }}>
                    <button
                        className="btn btn-primary"
                        onClick={handleCompute}
                        disabled={computing}
                    >
                        {computing ? 'Recomputing Metrics...' : 'Recompute Metrics'}
                    </button>
                </div>

                <div className="summary-cards">
                    <div className="summary-card">
                        <h4>Total VA Time</h4>
                        <p className="metric-value">{totalVASeconds.toFixed(1)}s</p>
                        <p className="metric-percent">{((totalVASeconds / totalSeconds) * 100).toFixed(1)}%</p>
                    </div>
                    <div className="summary-card">
                        <h4>Total NVA Time</h4>
                        <p className="metric-value">{totalNVASeconds.toFixed(1)}s</p>
                        <p className="metric-percent">{((totalNVASeconds / totalSeconds) * 100).toFixed(1)}%</p>
                    </div>
                    <div className="summary-card">
                        <h4>Total Time</h4>
                        <p className="metric-value">{totalSeconds.toFixed(1)}s</p>
                        <p className="metric-percent">100%</p>
                    </div>
                </div>

                <div className="charts-grid">
                    <div className="chart-card">
                        <h3>VA vs NVA Overview</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={pieData}
                                    cx="50%"
                                    cy="50%"
                                    labelLine={false}
                                    label={({ name, value, percent }) =>
                                        `${name}: ${(percent * 100).toFixed(1)}%`
                                    }
                                    outerRadius={100}
                                    fill="#8884d8"
                                    dataKey="value"
                                >
                                    {COLORS.map((color, index) => (
                                        <Cell key={`cell-${index}`} fill={color} />
                                    ))}
                                </Pie>
                                <Tooltip formatter={(value) => `${value.toFixed(1)}s`} />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="chart-card">
                        <h3>Worker Time Distribution</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={metrics}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="worker_id" />
                                <YAxis />
                                <Tooltip />
                                <Legend />
                                <Bar dataKey="va_seconds" fill="#10b981" name="VA (s)" />
                                <Bar dataKey="nva_seconds" fill="#ef4444" name="NVA (s)" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="metrics-table">
                    <h3>Detailed Metrics per Worker</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Worker ID</th>
                                <th>VA Frames</th>
                                <th>NVA Frames</th>
                                <th>VA Time (s)</th>
                                <th>NVA Time (s)</th>
                                <th>VA %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {metrics.map((metric) => (
                                <tr key={metric.worker_id}>
                                    <td className="worker-id">{metric.worker_id}</td>
                                    <td>{metric.va_frames}</td>
                                    <td>{metric.nva_frames}</td>
                                    <td>{metric.va_seconds.toFixed(2)}</td>
                                    <td>{metric.nva_seconds.toFixed(2)}</td>
                                    <td>
                                        <span className="percentage-badge" style={{
                                            backgroundColor: metric.va_percentage > 70 ? '#dcfce7' : '#fee2e2',
                                            color: metric.va_percentage > 70 ? '#166534' : '#991b1b'
                                        }}>
                                            {metric.va_percentage.toFixed(1)}%
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    )
}

export default Analytics

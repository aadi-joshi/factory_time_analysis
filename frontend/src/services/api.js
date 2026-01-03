import axios from 'axios'

const API_BASE_URL = '/api'

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
})

export const videosApi = {
    upload: (file) => {
        const formData = new FormData()
        formData.append('file', file)
        return apiClient.post('/videos/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
    },

    getAll: () => apiClient.get('/videos'),

    get: (videoId) => apiClient.get(`/videos/${videoId}`),

    getFirstFrame: (videoId) => `/api/videos/${videoId}/first-frame`,

    delete: (videoId) => apiClient.delete(`/videos/${videoId}`),

    process: (videoId) => apiClient.post(`/videos/${videoId}/process`),

    getSummary: (videoId) => apiClient.get(`/videos/${videoId}/summary`),
}

export const zonesApi = {
    create: (zoneData) => apiClient.post('/zones', zoneData),

    getByVideo: (videoId) => apiClient.get(`/videos/${videoId}/zones`),

    update: (zoneId, zoneData) => apiClient.put(`/zones/${zoneId}`, zoneData),

    delete: (zoneId) => apiClient.delete(`/zones/${zoneId}`),
}

export const workerZonesApi = {
    assign: (assignmentData) => apiClient.post('/worker-zones/assign', assignmentData),

    getByVideo: (videoId) => apiClient.get(`/videos/${videoId}/worker-zones`),

    update: (assignmentId, data) => apiClient.put(`/worker-zones/${assignmentId}`, data),

    delete: (assignmentId) => apiClient.delete(`/worker-zones/${assignmentId}`),
}

export const tracksApi = {
    getByVideo: (videoId) => apiClient.get(`/videos/${videoId}/tracks`),

    getFrameTracks: (videoId, frameIdx) => apiClient.get(`/videos/${videoId}/tracks?frame=${frameIdx}`),
}

export const mergesApi = {
    create: (mergeData) => apiClient.post('/id-merges', mergeData),

    getByVideo: (videoId) => apiClient.get(`/videos/${videoId}/id-merges`),
}

export const workersApi = {
    list: (videoId) => apiClient.get(`/videos/${videoId}/workers`),

    getImageUrl: (videoId, workerId) => `/api/videos/${videoId}/workers/${workerId}/image`,

    getFirstDetectionFrameUrl: (videoId, workerId) =>
        `/api/videos/${videoId}/workers/${workerId}/first-detection-frame`,
}

export const analyticsApi = {
    getMetrics: (videoId) => apiClient.get(`/videos/${videoId}/metrics`),

    computeMetrics: (videoId) => apiClient.post(`/videos/${videoId}/compute-metrics`),

    getWorkerTimeline: (videoId, workerId) =>
        apiClient.get(`/videos/${videoId}/worker-timeline/${workerId}`),
}

export default apiClient

import type {
  AdminOverview,
  Job,
  JobType,
  ModelRegistryItem,
  UsageSummary,
  User,
  EngineId,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const TOKEN_KEY = 'ai_studio_token'

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const err = await res.json()
      message = err.detail || message
    } catch {
      // ignore json parse error
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export const api = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; user: User }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  register: (email: string, password: string, display_name: string) =>
    apiFetch<{ access_token: string; user: User }>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),

  googleSignIn: (id_token: string, email?: string) =>
    apiFetch<{ access_token: string; user: User }>('/api/v1/auth/google', {
      method: 'POST',
      body: JSON.stringify({ id_token, email }),
    }),

  me: () => apiFetch<User>('/api/v1/auth/me'),

  uploadFile: async (
    file: File,
    purpose: 'portrait' | 'reference_image' | 'audio' | 'other'
  ): Promise<string> => {
    const signed = await apiFetch<{
      object_path: string
      upload_url: string
      headers: Record<string, string>
    }>('/api/v1/uploads', {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        purpose,
        size_bytes: file.size,
      }),
    })

    const putRes = await fetch(`${API_BASE}${signed.upload_url.startsWith('/') ? signed.upload_url : ''}`.replace(
      `${API_BASE}${signed.upload_url}`,
      signed.upload_url.startsWith('http') ? signed.upload_url : `${API_BASE}${signed.upload_url}`
    ), {
      method: 'PUT',
      headers: signed.headers,
      body: file,
    })
    if (!putRes.ok) {
      throw new Error('Failed to upload file to storage')
    }
    return signed.object_path
  },

  createJob: (payload: {
    job_type: JobType
    engine: EngineId
    idempotency_key: string
    params: Record<string, unknown>
  }) =>
    apiFetch<Job>('/api/v1/jobs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listJobs: (params?: { job_type?: string; state?: string }) => {
    const qs = new URLSearchParams()
    if (params?.job_type) qs.set('job_type', params.job_type)
    if (params?.state) qs.set('state', params.state)
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return apiFetch<Job[]>(`/api/v1/jobs${suffix}`)
  },

  getJob: (jobId: string) => apiFetch<Job>(`/api/v1/jobs/${jobId}`),

  retryJob: (jobId: string) =>
    apiFetch<Job>(`/api/v1/jobs/${jobId}/retry`, { method: 'POST' }),

  deleteJob: (jobId: string) =>
    apiFetch<Job>(`/api/v1/jobs/${jobId}`, { method: 'DELETE' }),

  getAssetDownloadUrl: async (assetId: string) => {
    const res = await apiFetch<{ download_url: string; filename: string; content_type: string }>(
      `/api/v1/assets/${assetId}/download`
    )
    const url = res.download_url.startsWith('http')
      ? res.download_url
      : `${API_BASE}${res.download_url}`
    return { ...res, download_url: url }
  },

  listModels: () => apiFetch<ModelRegistryItem[]>('/api/v1/models'),
  getUsage: () => apiFetch<UsageSummary>('/api/v1/usage'),

  // Admin
  adminOverview: () => apiFetch<AdminOverview>('/api/v1/admin/overview'),
  adminUsers: () => apiFetch<User[]>('/api/v1/admin/users'),
  adminUpdateUser: (userId: string, body: Partial<User>) =>
    apiFetch<User>(`/api/v1/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  adminJobs: (state?: string) =>
    apiFetch<Job[]>(`/api/v1/admin/jobs${state ? `?state=${state}` : ''}`),
  adminToggleModel: (modelId: string, enabled: boolean) =>
    apiFetch<ModelRegistryItem>(`/api/v1/admin/models/${modelId}`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),
}

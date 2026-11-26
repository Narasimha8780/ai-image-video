export type UserRole = 'customer' | 'admin'
export type JobType = 'image' | 'talking_video' | 'cinematic_video'
export type JobState = 'queued' | 'starting' | 'running' | 'uploading' | 'completed' | 'failed' | 'cancelled'
export type EngineId = 'flux_schnell' | 'sdxl' | 'liveportrait_musetalk' | 'wan2_2' | 'seedance' | 'kling'

export interface User {
  id: string
  email: string
  display_name: string
  role: UserRole
  credits: number
  daily_quota: number
  daily_used: number
  max_active_jobs: number
  is_active: boolean
  created_at: string
}

export interface AssetRef {
  asset_id: string
  object_path: string
  content_type: string
  filename: string
  size_bytes: number
  width?: number
  height?: number
  duration_seconds?: number
}

export interface Job {
  id: string
  user_id: string
  job_type: JobType
  engine: EngineId
  model_version: string
  state: JobState
  progress: number
  status_message: string
  params: Record<string, unknown>
  input_refs: string[]
  output_refs: AssetRef[]
  estimated_credits: number
  actual_credits?: number
  estimated_seconds: number
  retry_count: number
  error_category?: string
  error_message?: string
  provider_job_id?: string
  idempotency_key: string
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
  expires_at?: string
}

export interface ModelRegistryItem {
  id: EngineId
  name: string
  job_type: JobType
  provider: string
  version: string
  enabled: boolean
  is_premium: boolean
  base_credits: number
  notes: string
  license_note: string
}

export interface UsageTransaction {
  id: string
  user_id: string
  job_id?: string
  delta: number
  reason: string
  created_at: string
}

export interface UsageSummary {
  credits: number
  daily_quota: number
  daily_used: number
  max_active_jobs: number
  active_jobs: number
  transactions: UsageTransaction[]
}

export interface AdminOverview {
  total_users: number
  total_jobs: number
  active_queue_depth: number
  completed_jobs: number
  failed_jobs: number
  total_credits_consumed: number
}

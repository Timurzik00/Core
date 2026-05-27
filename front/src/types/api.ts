// Соответствуют схемам в app/schemas.py
export interface Agent {
  uuid: string
  family: string
  hostname: string
  version: string
  last_seen: string | null
  created_at: string | null
  last_applied_version: number | null
  last_error: string | null
  last_reported_at: string | null
}

export interface AgentsListResponse {
  agents: Agent[]
  total: number
  limit: number
  offset: number
}

export interface ConfigHistoryRecord {
  id: number
  config_version: number
  applied_at: string
  success: boolean
  error: string | null
  applied_by: string
  duration_seconds: number | null
}

export interface ManagedFileInfo {
  id: number
  file_path: string
  desired_content: string | null
  current_content: string | null
  is_in_sync: boolean
  last_synced_at: string | null
  last_checked_at: string | null
  config_version: number | null
}

export interface AgentConfigSnapshot {
  id: number
  snapshot: Record<string, any>
  config_version: number | null
  captured_at: string
  has_drift: boolean
  drift_summary: string | null
}

export interface AgentDetailed extends Agent {
  current_snapshot: AgentConfigSnapshot | null
  recent_history: ConfigHistoryRecord[]
}

export interface ConfigPayload {
  service?: string
  cli?: { binary: string; args: string }
  file?: { path: string; content: string }
}

export interface FamilyAgentsResponse {
  family: string
  count: number
  agents: Agent[]
}

export interface CommandResponse {
  id: number
  agent_uuid: string
  command_type: string
  params: Record<string, any>
  status: 'pending' | 'running' | 'done' | 'failed'
  result: Record<string, any> | null
  error: string | null
  created_at: string
  picked_at: string | null
  completed_at: string | null
}

export interface ReadFileResult {
  file_path: string
  content: string | null
  size: number | null
  status: string
  error: string | null
  completed_at: string | null
}

export interface DirEntry {
  name: string
  type: 'file' | 'dir' | 'error'
  size: number | null
  modified: number | null
  error: string | null
}

export interface ListDirResult {
  path: string
  entries: DirEntry[]
  total: number | null
  status: string
  error: string | null
  completed_at: string | null
}

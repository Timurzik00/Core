import axios from 'axios'
import type {
  Agent,
  AgentDetailed,
  AgentsListResponse,
  ConfigHistoryRecord,
  ManagedFileInfo,
  AgentConfigSnapshot,
  FamilyAgentsResponse,
  ConfigPayload,
  ReadFileResult,
  ListDirResult,
} from '@/types/api'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

// ── Agents ──
export const agentsApi = {
  list: async (params?: {
    family?: string
    hostname?: string
    sort_by?: string
    order?: string
    limit?: number
    offset?: number
  }): Promise<AgentsListResponse> => {
    const { data } = await client.get('/agents', { params })
    return data
  },

  get: async (uuid: string): Promise<AgentDetailed> => {
    const { data } = await client.get(`/agent/${uuid}`)
    return data
  },

  delete: async (uuid: string): Promise<void> => {
    await client.delete(`/agent/${uuid}`)
  },

  history: async (uuid: string, limit = 50): Promise<ConfigHistoryRecord[]> => {
    const { data } = await client.get(`/agent/${uuid}/history`, { params: { limit } })
    return data
  },

  failedHistory: async (uuid: string, limit = 50): Promise<ConfigHistoryRecord[]> => {
    const { data } = await client.get(`/agent/${uuid}/history/failed`, { params: { limit } })
    return data
  },

  files: async (uuid: string): Promise<ManagedFileInfo[]> => {
    const { data } = await client.get(`/agent/${uuid}/files`)
    return data
  },

  outOfSyncFiles: async (uuid: string): Promise<ManagedFileInfo[]> => {
    const { data } = await client.get(`/agent/${uuid}/files/out-of-sync`)
    return data
  },

  snapshot: async (uuid: string): Promise<AgentConfigSnapshot> => {
    const { data } = await client.get(`/agent/${uuid}/snapshot`)
    return data
  },

  snapshots: async (uuid: string, limit = 20): Promise<AgentConfigSnapshot[]> => {
    const { data } = await client.get(`/agent/${uuid}/snapshots`, { params: { limit } })
    return data
  },

  setConfig: async (uuid: string, configs: ConfigPayload[]) => {
    const { data } = await client.post(`/agent/${uuid}/config`, { configs })
    return data
  },

  getConfigVersion: async (uuid: string, version: number) => {
    const { data } = await client.get(`/agent/${uuid}/config/${version}`)
    return data as { version: number; created_at: string; config: any; applications: any[] }
  },

  getCurrentConfig: async (uuid: string) => {
    const { data } = await client.get(`/agent/${uuid}/config/current`)
    return data as { version: number; config: any }
  },

  readFile: async (uuid: string, path: string, timeout = 45): Promise<ReadFileResult> => {
    const { data } = await client.post(`/agent/${uuid}/exec/read-file`, null, {
      params: { path, timeout },
      timeout: (timeout + 5) * 1000,
    })
    return data
  },

  listDir: async (uuid: string, path: string, timeout = 45): Promise<ListDirResult> => {
    const { data } = await client.post(`/agent/${uuid}/exec/list-dir`, null, {
      params: { path, timeout },
      timeout: (timeout + 5) * 1000,
    })
    return data
  },

  listCommands: async (uuid: string, limit = 100, status_filter?: string) => {
    const { data } = await client.get(`/agent/${uuid}/commands`, {
      params: { limit, status_filter },
    })
    return data as CommandRecord[]
  },

  changeFamily: async (uuid: string, family: string) => {
    const { data } = await client.put(`/agent/${uuid}/family`, { family })
    return data
  },

  bulkChangeFamily: async (uuids: string[], family: string) => {
    const { data } = await client.put('/agents/bulk-family', { uuids, family })
    return data as { updated: number; not_found: string[] }
  },

  rollback: async (uuid: string, version: number) => {
    const { data } = await client.post(`/agent/${uuid}/config/${version}/rollback`)
    return data as { created: { version: number; config: any }[]; total: number }
  },
}

// ── Commands ──
export interface CommandRecord {
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

export interface CommandListItem extends CommandRecord {
  agent_hostname: string
  agent_family: string
}

export const commandsApi = {
  listAll: async (params?: {
    limit?: number
    status_filter?: string
    command_type?: string
  }): Promise<CommandListItem[]> => {
    const { data } = await client.get('/commands', { params })
    return data
  },
}

// ── Families ──
export const familiesApi = {
  agents: async (family: string): Promise<FamilyAgentsResponse> => {
    const { data } = await client.get(`/family/${family}/agents`)
    return data
  },

  pushConfig: async (family: string, configs: ConfigPayload[]) => {
    const { data } = await client.post(`/family/${family}/config`, { configs })
    return data
  },

  history: async (family: string, limit = 100) => {
    const { data } = await client.get(`/family/${family}/history`, { params: { limit } })
    return data
  },

  filesStatus: async (family: string) => {
    const { data } = await client.get(`/family/${family}/files-status`)
    return data
  },

  rename: async (family: string, newName: string) => {
    const { data } = await client.put(`/family/${family}/rename`, { new_name: newName })
    return data as { family: string; agents_affected: number; message: string }
  },

  delete: async (family: string) => {
    const { data } = await client.delete(`/family/${family}`)
    return data as { family: string; agents_affected: number; message: string }
  },
}

// ── System ──
export const systemApi = {
  health: async () => {
    const { data } = await client.get('/health')
    return data
  },

  globalHistory: async (params?: { limit?: number; success?: boolean; family?: string }) => {
    const { data } = await client.get('/history', { params })
    return data as GlobalHistoryRecord[]
  },
}

export interface GlobalHistoryRecord {
  id: number
  agent_uuid: string
  agent_hostname: string
  agent_family: string
  config_version: number
  applied_at: string
  success: boolean
  error: string | null
  applied_by: string
  duration_seconds: number | null
}

// ── Service Presets ──
export interface ServicePreset {
  id: number
  service: string
  file_path: string | null
  cli_binary: string | null
  cli_args: string | null
  content_template: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface ServicePresetInput {
  service?: string
  file_path?: string | null
  cli_binary?: string | null
  cli_args?: string | null
  content_template?: string | null
  description?: string | null
}

export const presetsApi = {
  list: async (): Promise<ServicePreset[]> => {
    const { data } = await client.get('/service-presets')
    return data
  },

  create: async (preset: ServicePresetInput & { service: string }): Promise<ServicePreset> => {
    const { data } = await client.post('/service-presets', preset)
    return data
  },

  update: async (id: number, patch: ServicePresetInput): Promise<ServicePreset> => {
    const { data } = await client.put(`/service-presets/${id}`, patch)
    return data
  },

  delete: async (id: number): Promise<void> => {
    await client.delete(`/service-presets/${id}`)
  },
}

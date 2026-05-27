import type { ConfigPayload } from '@/types/api'

/**
 * Core хранит конфиг агента либо как одиночный объект {service, file, cli},
 * либо как обёртку {configs: [...]} (мульти-сервис).
 * Эта функция приводит к единому виду — всегда массив.
 */
export function extractConfigsList(desired: any): ConfigPayload[] {
  if (!desired || typeof desired !== 'object') return []
  if (Array.isArray(desired.configs)) return desired.configs as ConfigPayload[]
  // Одиночный конфиг (legacy) — обернём в массив
  if (desired.file || desired.cli) return [desired as ConfigPayload]
  return []
}

import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Парсит дату от Core API.
 * Core отдаёт naive datetime без таймзоны (datetime.utcnow()) — например "2026-05-22T10:30:15.123".
 * Браузер по умолчанию считает такую строку локальным временем, что ломает расчёты.
 * Здесь принудительно интерпретируем как UTC.
 */
export function parseApiDate(date: string | Date): Date {
  if (date instanceof Date) return date
  // Если строка уже с таймзоной (Z или +/-HH:MM) — браузер сам разберётся
  if (/[Zz]$|[+-]\d{2}:?\d{2}$/.test(date)) return new Date(date)
  // Иначе считаем UTC: добавляем Z
  return new Date(date + 'Z')
}

export function formatRelativeTime(date: string | Date): string {
  const d = parseApiDate(date)
  const diff = Date.now() - d.getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 0) return 'in the future'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function formatDateTime(date: string | Date): string {
  return parseApiDate(date).toLocaleString()
}


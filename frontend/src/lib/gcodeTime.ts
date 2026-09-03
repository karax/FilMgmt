export function formatGCodeDuration(seconds: number, locale: string): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  if (seconds < 60) {
    const roundedSeconds = Math.round(seconds)
    return locale.startsWith('pt') ? `${roundedSeconds} s` : `${roundedSeconds} sec`
  }

  let totalMinutes = Math.round(seconds / 60)
  const days = Math.floor(totalMinutes / (24 * 60))
  totalMinutes -= days * 24 * 60
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days} d`)
  if (hours > 0) parts.push(locale.startsWith('pt') ? `${hours} h` : `${hours} hr`)
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes} min`)
  return parts.join(' ')
}

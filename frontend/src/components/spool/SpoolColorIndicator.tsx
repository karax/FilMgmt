interface SpoolColorIndicatorProps {
  colorHex: string | null
  colorName: string
  className?: string
}

export function SpoolColorIndicator({
  colorHex,
  colorName,
  className = '',
}: SpoolColorIndicatorProps) {
  return (
    <span
      aria-label={`Color: ${colorName}`}
      className={`size-3.5 shrink-0 rounded-full border border-black/15 shadow-sm dark:border-white/20 ${
        colorHex ? '' : 'bg-line'
      } ${className}`}
      style={colorHex ? { backgroundColor: colorHex } : undefined}
    />
  )
}

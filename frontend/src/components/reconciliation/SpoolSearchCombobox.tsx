import { ChevronDown, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ReconciliationSpoolOption } from '../../types/reconciliation'

type Props = {
  label: string
  onSelect: (spoolId: number) => void
  onSkip: () => void
  selectedSpoolId: number | null
  skipped: boolean
  spools: ReconciliationSpoolOption[]
  suggestedSpoolIds: number[]
}

type Choice = { kind: 'spool'; spool: ReconciliationSpoolOption } | { kind: 'skip' }

export function SpoolSearchCombobox({
  label,
  onSelect,
  onSkip,
  selectedSpoolId,
  skipped,
  spools,
  suggestedSpoolIds,
}: Props) {
  const { t } = useTranslation()
  const inputId = useId()
  const listboxId = `${inputId}-listbox`
  const selectedSpool = spools.find((spool) => spool.id === selectedSpoolId)
  const selectedLabel = selectedSpool ? spoolLabel(selectedSpool) : ''
  const skipLabel = t('reconciliation.doNotDeduct')
  const [query, setQuery] = useState(skipped ? skipLabel : selectedLabel)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)

  useEffect(() => {
    if (open) return
    setQuery(skipped ? skipLabel : selectedLabel)
  }, [open, selectedLabel, skipLabel, skipped])

  const normalizedQuery = normalizeSearch(
    selectedSpool && query === selectedLabel ? '' : query,
  )
  const filtered = useMemo(
    () => spools.filter((spool) => matchesSearch(spoolSearchText(spool), normalizedQuery)),
    [normalizedQuery, spools],
  )
  const suggestedSet = useMemo(() => new Set(suggestedSpoolIds), [suggestedSpoolIds])
  const suggested = filtered.filter((spool) => suggestedSet.has(spool.id))
  const others = filtered.filter((spool) => !suggestedSet.has(spool.id))
  const showSkip = !normalizedQuery || normalizeSearch(skipLabel).includes(normalizedQuery)
  const choices: Choice[] = [
    ...suggested.map((spool): Choice => ({ kind: 'spool', spool })),
    ...others.map((spool): Choice => ({ kind: 'spool', spool })),
    ...(showSkip ? [{ kind: 'skip' } as Choice] : []),
  ]

  function choose(choice: Choice) {
    if (choice.kind === 'skip') {
      onSkip()
      setQuery(skipLabel)
    } else {
      onSelect(choice.spool.id)
      setQuery(spoolLabel(choice.spool))
    }
    setOpen(false)
    setActiveIndex(-1)
  }

  function restoreSelection() {
    setQuery(skipped ? skipLabel : selectedLabel)
    setOpen(false)
    setActiveIndex(-1)
  }

  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) restoreSelection()
      }}
    >
      <label className="text-sm font-medium text-ink" htmlFor={inputId}>{label}</label>
      <div className="relative mt-1.5">
        <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
        <input
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          aria-haspopup="listbox"
          className="w-full rounded-md border border-line bg-surface py-2.5 pl-9 pr-9 text-sm text-ink placeholder:text-ink-muted"
          id={inputId}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
            setActiveIndex(-1)
          }}
          onFocus={(event) => {
            setOpen(true)
            event.currentTarget.select()
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault()
              restoreSelection()
              return
            }
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault()
              setOpen(true)
              if (!choices.length) return
              setActiveIndex((current) => {
                if (event.key === 'ArrowDown') return current >= choices.length - 1 ? 0 : current + 1
                return current <= 0 ? choices.length - 1 : current - 1
              })
              return
            }
            if (event.key === 'Enter' && open && activeIndex >= 0 && choices[activeIndex]) {
              event.preventDefault()
              choose(choices[activeIndex])
            }
          }}
          placeholder={t('reconciliation.searchSpoolPlaceholder')}
          role="combobox"
          type="search"
          value={query}
        />
        <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
      </div>

      {open && (
        <div className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-line bg-surface p-1 shadow-lg" id={listboxId} role="listbox">
          {!choices.length && <p className="px-3 py-3 text-sm text-ink-muted">{t('reconciliation.noSpoolMatches')}</p>}
          <SpoolGroup
            activeIndex={activeIndex}
            choices={choices}
            label={t('reconciliation.suggestedSpools')}
            onChoose={choose}
            selectedSpoolId={selectedSpoolId}
            spools={suggested}
          />
          <SpoolGroup
            activeIndex={activeIndex}
            choices={choices}
            label={t('reconciliation.otherInventory')}
            onChoose={choose}
            selectedSpoolId={selectedSpoolId}
            spools={others}
          />
          {showSkip && (
            <button
              aria-selected={skipped}
              className={optionClass(activeIndex === choices.length - 1)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose({ kind: 'skip' })}
              role="option"
              type="button"
            >
              {skipLabel}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function SpoolGroup({
  activeIndex,
  choices,
  label,
  onChoose,
  selectedSpoolId,
  spools,
}: {
  activeIndex: number
  choices: Choice[]
  label: string
  onChoose: (choice: Choice) => void
  selectedSpoolId: number | null
  spools: ReconciliationSpoolOption[]
}) {
  if (!spools.length) return null
  return (
    <div aria-label={label} role="group">
      <p className="px-3 pb-1 pt-2 text-[0.68rem] font-semibold uppercase tracking-wide text-ink-muted">{label}</p>
      {spools.map((spool) => {
        const index = choices.findIndex((choice) => choice.kind === 'spool' && choice.spool.id === spool.id)
        return (
          <button
            aria-selected={selectedSpoolId === spool.id}
            className={optionClass(index === activeIndex)}
            key={spool.id}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onChoose({ kind: 'spool', spool })}
            role="option"
            type="button"
          >
            {spoolLabel(spool)}
          </button>
        )
      })}
    </div>
  )
}

function optionClass(active: boolean): string {
  return `block w-full rounded px-3 py-2 text-left text-sm text-ink ${active ? 'bg-accent-soft' : 'hover:bg-surface-raised'}`
}

function spoolLabel(spool: ReconciliationSpoolOption): string {
  const name = spool.display_name ? ` · ${spool.display_name}` : ''
  return `${spool.code}${name} · ${spool.manufacturer_name} ${spool.material_name} ${spool.color_name} · ${formatWeight(spool.current_filament_weight_g)} g`
}

function spoolSearchText(spool: ReconciliationSpoolOption): string {
  return normalizeSearch([
    spool.code,
    spool.display_name,
    spool.manufacturer_name,
    spool.material_name,
    spool.color_name,
  ].filter(Boolean).join(' '))
}

function normalizeSearch(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().trim()
}

function matchesSearch(searchText: string, query: string): boolean {
  return query.split(/\s+/).filter(Boolean).every((term) => searchText.includes(term))
}

function formatWeight(value: string | number): string {
  const number = Number(value)
  return Number.isFinite(number)
    ? number.toLocaleString(undefined, { maximumFractionDigits: 3 })
    : String(value)
}

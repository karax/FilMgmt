import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, ChevronLeft, LoaderCircle, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { isApiError } from '../api/client'
import { createManufacturer, deleteManufacturer, updateManufacturer } from '../api/manufacturers'
import { createMaterial, deleteMaterial, type MaterialPayload, updateMaterial } from '../api/materials'
import { manufacturersQueryKey, useManufacturers } from '../hooks/useManufacturers'
import { materialsQueryKey, useMaterials } from '../hooks/useMaterials'
import type { Manufacturer, Material } from '../types/spool'

const inputClass = 'mt-1.5 w-full rounded-md border border-line bg-surface px-3 py-2.5 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent/20'

function messageFor(error: unknown, t: (key: string) => string) {
  if (isApiError(error) && error.status === 409) return t('catalogs.errors.inUseOrDuplicate')
  if (isApiError(error) && error.status === 422) return t('catalogs.errors.validation')
  return t('catalogs.errors.save')
}

export function CatalogsPage() {
  const { t } = useTranslation()
  const manufacturers = useManufacturers()
  const materials = useMaterials()
  return (
    <section aria-labelledby="catalogs-title" className="mx-auto max-w-5xl">
      <Link className="inline-flex items-center gap-1 text-sm font-semibold text-accent" to="/settings"><ChevronLeft className="size-4" />{t('catalogs.back')}</Link>
      <p className="mt-5 font-mono text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-accent">{t('catalogs.eyebrow')}</p>
      <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl" id="catalogs-title">{t('catalogs.title')}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted sm:text-base">{t('catalogs.description')}</p>
      <div className="mt-8 grid items-start gap-6 lg:grid-cols-2">
        <ManufacturerSection query={manufacturers} />
        <MaterialSection query={materials} />
      </div>
      <p className="mt-6 rounded-md border border-line bg-surface-raised p-4 text-sm leading-6 text-ink-muted">{t('catalogs.locationNote')}</p>
    </section>
  )
}

type CatalogQuery<T> = { data?: T[]; error: unknown; isPending: boolean; isFetching: boolean; refetch: () => unknown }

function ManufacturerSection({ query }: { query: CatalogQuery<Manufacturer> }) {
  const { t } = useTranslation(); const client = useQueryClient()
  const [editing, setEditing] = useState<Manufacturer | null | undefined>(undefined)
  const mutation = useMutation({ mutationFn: async (value: { item?: Manufacturer; name: string; website: string }) => value.item ? updateManufacturer(value.item.id, { name: value.name, website: value.website.trim() || null }) : createManufacturer({ name: value.name, website: value.website.trim() || null }), onSuccess: async () => { await client.invalidateQueries({ queryKey: manufacturersQueryKey }); setEditing(undefined) } })
  const removal = useMutation({ mutationFn: deleteManufacturer, onSuccess: () => client.invalidateQueries({ queryKey: manufacturersQueryKey }) })
  return <CatalogPanel title={t('catalogs.manufacturers.title')} description={t('catalogs.manufacturers.description')} isLoading={query.isPending} error={query.error} retry={() => void query.refetch()} add={() => setEditing(null)} addLabel={t('catalogs.manufacturers.add')}>
    {editing !== undefined && <ManufacturerForm key={editing?.id ?? 'new'} item={editing} pending={mutation.isPending} error={mutation.error} cancel={() => { mutation.reset(); setEditing(undefined) }} submit={(value) => mutation.mutate(value)} />}
    {!query.isPending && !query.error && query.data?.length === 0 && <Empty title={t('catalogs.manufacturers.empty')} description={t('catalogs.manufacturers.emptyDescription')} action={t('catalogs.manufacturers.add')} onAction={() => setEditing(null)} />}
    <ul className="divide-y divide-line">{query.data?.map(item => <li className="flex min-w-0 items-center gap-3 py-3" key={item.id}><div className="min-w-0 flex-1"><p className="truncate font-semibold text-ink">{item.name}</p><p className="truncate text-xs text-ink-muted">{item.website ?? t('common.unconfigured')}</p></div><IconButton label={t('common.edit')} onClick={() => setEditing(item)} icon={Pencil}/><IconButton label={t('common.delete')} onClick={() => { if (window.confirm(t('catalogs.deleteConfirm', { name: item.name }))) removal.mutate(item.id) }} icon={Trash2}/></li>)}</ul>
    {removal.error && <ErrorText>{messageFor(removal.error, t)}</ErrorText>}
  </CatalogPanel>
}

function ManufacturerForm({ item, pending, error, cancel, submit }: { item: Manufacturer | null; pending: boolean; error: unknown; cancel: () => void; submit: (value: { item?: Manufacturer; name: string; website: string }) => void }) {
  const { t } = useTranslation(); const [name, setName] = useState(item?.name ?? ''); const [website, setWebsite] = useState(item?.website ?? '')
  const save = (event: FormEvent) => { event.preventDefault(); if (name.trim()) submit({ item: item ?? undefined, name: name.trim(), website }) }
  return <form className="mb-4 rounded-md border border-line bg-surface-raised p-4" onSubmit={save}><div className="flex items-center justify-between"><h4 className="font-semibold text-ink">{item ? t('catalogs.manufacturers.edit') : t('catalogs.manufacturers.add')}</h4><IconButton label={t('common.cancel')} onClick={cancel} icon={X}/></div><label className="mt-3 block text-sm font-semibold text-ink">{t('catalogs.fields.name')}<input autoFocus className={inputClass} maxLength={150} onChange={e => setName(e.target.value)} required value={name}/></label><label className="mt-3 block text-sm font-semibold text-ink">{t('catalogs.fields.website')}<input className={inputClass} onChange={e => setWebsite(e.target.value)} placeholder="https://" type="url" value={website}/></label>{Boolean(error) && <ErrorText>{messageFor(error, t)}</ErrorText>}<SaveButton pending={pending}/></form>
}

function MaterialSection({ query }: { query: CatalogQuery<Material> }) {
  const { t } = useTranslation(); const client = useQueryClient(); const [editing, setEditing] = useState<Material | null | undefined>(undefined)
  const mutation = useMutation({ mutationFn: async (value: { item?: Material; payload: MaterialPayload }) => value.item ? updateMaterial(value.item.id, value.payload) : createMaterial(value.payload), onSuccess: async () => { await client.invalidateQueries({ queryKey: materialsQueryKey }); setEditing(undefined) } })
  const removal = useMutation({ mutationFn: deleteMaterial, onSuccess: () => client.invalidateQueries({ queryKey: materialsQueryKey }) })
  return <CatalogPanel title={t('catalogs.materials.title')} description={t('catalogs.materials.description')} isLoading={query.isPending} error={query.error} retry={() => void query.refetch()} add={() => setEditing(null)} addLabel={t('catalogs.materials.add')}>
    {editing !== undefined && <MaterialForm key={editing?.id ?? 'new'} item={editing} pending={mutation.isPending} error={mutation.error} cancel={() => { mutation.reset(); setEditing(undefined) }} submit={(value) => mutation.mutate(value)} />}
    {!query.isPending && !query.error && query.data?.length === 0 && <Empty title={t('catalogs.materials.empty')} description={t('catalogs.materials.emptyDescription')} action={t('catalogs.materials.add')} onAction={() => setEditing(null)} />}
    <ul className="divide-y divide-line">{query.data?.map(item => <li className="flex min-w-0 items-center gap-3 py-3" key={item.id}><div className="min-w-0 flex-1"><p className="truncate font-semibold text-ink">{item.name}</p><p className="text-xs text-ink-muted">{item.category}{item.density_g_cm3 ? ` · ${item.density_g_cm3} g/cm³` : ''}</p></div><IconButton label={t('common.edit')} onClick={() => setEditing(item)} icon={Pencil}/><IconButton label={t('common.delete')} onClick={() => { if (window.confirm(t('catalogs.deleteConfirm', { name: item.name }))) removal.mutate(item.id) }} icon={Trash2}/></li>)}</ul>
    {removal.error && <ErrorText>{messageFor(removal.error, t)}</ErrorText>}
  </CatalogPanel>
}

const numberOrNull = (value: string) => value === '' ? null : Number(value)
function MaterialForm({ item, pending, error, cancel, submit }: { item: Material | null; pending: boolean; error: unknown; cancel: () => void; submit: (value: { item?: Material; payload: MaterialPayload }) => void }) {
  const { t } = useTranslation(); const [form, setForm] = useState({ name: item?.name ?? '', category: item?.category ?? '', density: item?.density_g_cm3 == null ? '' : String(item.density_g_cm3), nozzleMin: item?.default_nozzle_temp_min == null ? '' : String(item.default_nozzle_temp_min), nozzleMax: item?.default_nozzle_temp_max == null ? '' : String(item.default_nozzle_temp_max), bedMin: item?.default_bed_temp_min == null ? '' : String(item.default_bed_temp_min), bedMax: item?.default_bed_temp_max == null ? '' : String(item.default_bed_temp_max), notes: item?.notes ?? '' })
  const set = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }))
  const save = (event: FormEvent) => { event.preventDefault(); submit({ item: item ?? undefined, payload: { name: form.name.trim(), category: form.category.trim(), density_g_cm3: numberOrNull(form.density), default_nozzle_temp_min: numberOrNull(form.nozzleMin), default_nozzle_temp_max: numberOrNull(form.nozzleMax), default_bed_temp_min: numberOrNull(form.bedMin), default_bed_temp_max: numberOrNull(form.bedMax), notes: form.notes.trim() || null } }) }
  return <form className="mb-4 rounded-md border border-line bg-surface-raised p-4" onSubmit={save}><div className="flex items-center justify-between"><h4 className="font-semibold text-ink">{item ? t('catalogs.materials.edit') : t('catalogs.materials.add')}</h4><IconButton label={t('common.cancel')} onClick={cancel} icon={X}/></div><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="text-sm font-semibold text-ink">{t('catalogs.fields.name')}<input autoFocus className={inputClass} maxLength={100} onChange={e => set('name', e.target.value)} required value={form.name}/></label><label className="text-sm font-semibold text-ink">{t('catalogs.fields.category')}<input className={inputClass} maxLength={50} onChange={e => set('category', e.target.value)} required value={form.category}/></label><label className="text-sm font-semibold text-ink sm:col-span-2">{t('catalogs.fields.density')}<input className={inputClass} max="10" min="0.001" onChange={e => set('density', e.target.value)} step="0.001" type="number" value={form.density}/><span className="mt-1 block text-xs font-normal leading-5 text-ink-muted">{t('catalogs.fields.densityHelp')}</span></label><Temperature label={t('catalogs.fields.nozzle')} min={form.nozzleMin} max={form.nozzleMax} setMin={v => set('nozzleMin', v)} setMax={v => set('nozzleMax', v)}/><Temperature label={t('catalogs.fields.bed')} min={form.bedMin} max={form.bedMax} setMin={v => set('bedMin', v)} setMax={v => set('bedMax', v)}/></div><label className="mt-3 block text-sm font-semibold text-ink">{t('catalogs.fields.notes')}<textarea className={`${inputClass} min-h-20`} onChange={e => set('notes', e.target.value)} value={form.notes}/></label>{Boolean(error) && <ErrorText>{messageFor(error, t)}</ErrorText>}<SaveButton pending={pending}/></form>
}

function Temperature({ label, min, max, setMin, setMax }: { label: string; min: string; max: string; setMin: (v: string) => void; setMax: (v: string) => void }) { const { t } = useTranslation(); return <fieldset><legend className="text-sm font-semibold text-ink">{label}</legend><div className="grid grid-cols-2 gap-2"><label className="text-xs text-ink-muted">{t('catalogs.fields.minimum')}<input className={inputClass} max="500" min="0" onChange={e => setMin(e.target.value)} type="number" value={min}/></label><label className="text-xs text-ink-muted">{t('catalogs.fields.maximum')}<input className={inputClass} max="500" min="0" onChange={e => setMax(e.target.value)} type="number" value={max}/></label></div></fieldset> }

function CatalogPanel({ title, description, children, add, addLabel, isLoading, error, retry }: { title: string; description: string; children: React.ReactNode; add: () => void; addLabel: string; isLoading: boolean; error: unknown; retry: () => void }) { const { t } = useTranslation(); return <section className="min-w-0 rounded-lg border border-line bg-surface p-4 shadow-sm sm:p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold text-ink">{title}</h3><p className="mt-1 text-sm leading-5 text-ink-muted">{description}</p></div><button className="inline-flex min-h-10 items-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-semibold text-sidebar" onClick={add} type="button"><Plus className="size-4"/>{addLabel}</button></div><div className="mt-4">{isLoading && <p className="flex items-center gap-2 text-sm text-ink-muted" role="status"><LoaderCircle className="size-4 animate-spin"/>{t('common.loading')}</p>}{Boolean(error) && <div role="alert"><ErrorText>{t('catalogs.errors.load')}</ErrorText><button className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-accent" onClick={retry}><RefreshCw className="size-4"/>{t('common.retry')}</button></div>}{children}</div></section> }
function Empty({ title, description, action, onAction }: { title: string; description: string; action: string; onAction: () => void }) { return <div className="rounded-md border border-dashed border-line px-4 py-8 text-center"><p className="font-semibold text-ink">{title}</p><p className="mt-1 text-sm leading-5 text-ink-muted">{description}</p><button className="mt-4 text-sm font-semibold text-accent underline underline-offset-4" onClick={onAction}>{action}</button></div> }
function IconButton({ label, onClick, icon: Icon }: { label: string; onClick: () => void; icon: typeof Pencil }) { return <button aria-label={label} className="grid size-10 shrink-0 place-items-center rounded-md border border-line text-ink hover:bg-surface-raised" onClick={onClick} type="button"><Icon className="size-4"/></button> }
function SaveButton({ pending }: { pending: boolean }) { const { t } = useTranslation(); return <button className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-sidebar disabled:opacity-60" disabled={pending} type="submit">{pending && <LoaderCircle className="size-4 animate-spin"/>}{pending ? t('common.saving') : t('common.save')}</button> }
function ErrorText({ children }: { children: React.ReactNode }) { return <p className="mt-3 flex items-start gap-2 text-sm text-red-600 dark:text-red-400" role="alert"><AlertCircle className="mt-0.5 size-4 shrink-0"/>{children}</p> }

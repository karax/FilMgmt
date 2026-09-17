import { type FormEvent, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { normalizePrintSaveError, type PrintSaveErrors, type SaveRow } from '../../lib/printSaveErrors'
import { formatCurrency, formatPercent, formatWeight } from '../../lib/inventory'
import { calculateEstimatedMaterialCost, sumEstimatedCostsByCurrency } from '../../lib/printCost'
import type { ApiDecimal, PrintJobPayload, PrintJobSpoolPayload } from '../../types/printJob'
import type { Spool } from '../../types/spool'

type Row = { key: number; spoolId: string; estimatedWeight: string }
type Values = { name: string; spools: Row[]; hours: string; minutes: string; printerName: string; notes: string }
export type PrintFormInitial = Omit<Pick<PrintJobPayload, 'name' | 'estimated_time_minutes' | 'printer_name' | 'notes'>, 'spools'> & { spools: { spool_id:number; estimated_weight_g:ApiDecimal|null }[] }
export interface PrintJobFormProps { mode:'create'|'edit'; spools:Spool[]; initialValues?:PrintFormInitial; isSubmitting:boolean; submitError:unknown; onCancel:()=>void; onSubmit:(payload:PrintJobPayload)=>void }
const input='mt-1 min-w-0 w-full rounded-md border border-line bg-surface px-3 py-2.5 text-sm text-ink'
const newRow=(key:number):Row=>({key,spoolId:'',estimatedWeight:''})
export function printJobFormValues(job: PrintFormInitial): PrintFormInitial { return job }
function label(s:Spool) { return s.display_name ? `${s.display_name} — ${s.code}` : `${s.code} — ${s.manufacturer.name} ${s.material.name}` }
export function PrintJobForm({spools,initialValues,isSubmitting,onCancel,onSubmit,mode,submitError}:PrintJobFormProps) {
 const {t}=useTranslation(); const [next,setNext]=useState(()=>Math.max(2,(initialValues?.spools.length??0)+1)); const [errors,setErrors]=useState<PrintSaveErrors>({formError:'',fieldErrors:{}})
 const formRef=useRef<HTMLFormElement>(null)
 const locked=useRef(false)
 const submittedRows=useRef<SaveRow[]|null>(null)
 const handledError=useRef<unknown>(null)
 const handledTranslation=useRef(t)
 const focusFailure=useRef(false)
 const [v,setV]=useState<Values>(()=>{const rows=(initialValues?.spools??[]).map((s,i)=>({key:i+1,spoolId:String(s.spool_id),estimatedWeight:s.estimated_weight_g==null?'':String(s.estimated_weight_g)})); return {name:initialValues?.name??'',spools:rows.length?rows:[newRow(1)],hours:initialValues?.estimated_time_minutes==null?'':String(Math.floor(initialValues.estimated_time_minutes/60)),minutes:initialValues?.estimated_time_minutes==null?'':String(initialValues.estimated_time_minutes%60),printerName:initialValues?.printer_name??'',notes:initialValues?.notes??''}})

 useEffect(()=>{
   if(!isSubmitting) locked.current=false
 },[isSubmitting])
 useEffect(()=>{
   if(!submitError) { handledError.current=null; return }
   if(handledError.current===submitError&&handledTranslation.current===t) return
   handledError.current=submitError
   handledTranslation.current=t
   locked.current=false
   focusFailure.current=true
   setErrors(normalizePrintSaveError(submitError,submittedRows.current??v.spools,t))
 },[submitError,t,v.spools])
 useLayoutEffect(()=>{
   if(!focusFailure.current||!errors.formError||isSubmitting) return
   formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"], [data-save-alert]')?.focus()
   focusFailure.current=false
 },[errors,isSubmitting])
 const clear=(fields:string[])=>setErrors(current=>{
   const fieldErrors={...current.fieldErrors}
   fields.forEach(field=>delete fieldErrors[field])
   return {...current,fieldErrors}
 })
 const update=(patch:Partial<Values>)=>{
   const fields:Record<string,string>={name:'name',printerName:'printer_name',notes:'notes',hours:'estimated_time_minutes',minutes:'estimated_time_minutes'}
   clear(Object.keys(patch).flatMap(key=>fields[key]?[fields[key]]:key==='spools'?Object.keys(errors.fieldErrors).filter(field=>field.startsWith('spools.')&&!patch.spools?.some(row=>field.startsWith(`spools.${row.key}.`))):[]))
   setV(x=>({...x,...patch}))
 }
 const updateRow=(key:number,patch:Partial<Row>)=>{
   clear(Object.keys(patch).map(field=>`spools.${key}.${field==='spoolId'?'spool_id':'estimated_weight_g'}`))
   setV(x=>({...x,spools:x.spools.map(r=>r.key===key?{...r,...patch}:r)}))
 }
 const attrs=(field:string)=>({id:`print-${field}`,'aria-label':field==='estimated_time_minutes'?undefined:t(`prints.form.${field==='printer_name'?'printer':field.endsWith('.spool_id')?'spool':field.endsWith('.estimated_weight_g')?'estimatedWeight':field}`),'aria-invalid':Boolean(errors.fieldErrors[field]),'aria-describedby':errors.fieldErrors[field]?`print-${field}-error`:undefined,disabled:isSubmitting})
 const message=(field:string)=>errors.fieldErrors[field]?<span className="mt-1 block text-sm text-red-600 dark:text-red-400" id={`print-${field}-error`}>{errors.fieldErrors[field]}</span>:null
 const chosen=(id:string,key:number)=>v.spools.some(r=>r.key!==key&&r.spoolId===id)
 const previews=v.spools.map(row=>{const spool=spools.find(item=>item.id===Number(row.spoolId));const numericWeight=Number(row.estimatedWeight);const hasValidWeight=row.estimatedWeight.trim()!==''&&Number.isFinite(numericWeight)&&numericWeight>=0;const cost=spool&&hasValidWeight?calculateEstimatedMaterialCost(spool.purchase_price,spool.initial_filament_weight_g,row.estimatedWeight):null;return {key:row.key,spool,hasValidWeight,cost}})
 const totals=sumEstimatedCostsByCurrency(previews.flatMap(preview=>preview.spool&&preview.cost?[{currency:preview.spool.currency,materialCost:preview.cost.materialCost}]:[]))
 const unavailableCount=previews.filter(preview=>preview.spool&&preview.hasValidWeight&&!preview.cost).length

 const submit=(event:FormEvent)=>{
   event.preventDefault()
   if(locked.current||isSubmitting) return
   const fieldErrors:Record<string,string>={}
   const rows:PrintJobSpoolPayload[]=[]
   if(!v.name.trim()) fieldErrors.name=t('prints.form.errors.name')
   for(const row of v.spools){
     const weight=row.estimatedWeight.trim()===''?null:Number(row.estimatedWeight)
     if(!row.spoolId) fieldErrors[`spools.${row.key}.spool_id`]=t('prints.form.errors.spool')
     else if(rows.some(item=>item.spool_id===Number(row.spoolId))) fieldErrors[`spools.${row.key}.spool_id`]=t('prints.form.duplicateSpool')
     if(weight!==null&&(!Number.isFinite(weight)||weight<=0)) fieldErrors[`spools.${row.key}.estimated_weight_g`]=t('prints.form.errors.weight')
     rows.push({spool_id:Number(row.spoolId),estimated_weight_g:weight})
   }
   const h=v.hours===''?0:Number(v.hours),m=v.minutes===''?0:Number(v.minutes)
   if(!Number.isInteger(h)||h<0) fieldErrors.estimated_time_minutes=t('prints.form.errors.hours')
   else if(!Number.isInteger(m)||m<0||m>59) fieldErrors.estimated_time_minutes=t('prints.form.errors.minutes')
   else if((v.hours||v.minutes)&&h*60+m<=0) fieldErrors.estimated_time_minutes=t('prints.form.errors.duration')
   if(Object.keys(fieldErrors).length){focusFailure.current=true;setErrors({formError:t('prints.form.correctFields'),fieldErrors});return}
   setErrors({formError:'',fieldErrors:{}})
   submittedRows.current=v.spools.map(row=>({...row}))
   locked.current=true
   try{
     onSubmit({name:v.name.trim(),spools:rows,estimated_time_minutes:v.hours||v.minutes?h*60+m:null,printer_name:v.printerName.trim()||null,notes:v.notes.trim()||null})
   }catch(error){
     locked.current=false
     focusFailure.current=true
     setErrors(normalizePrintSaveError(error,submittedRows.current,t))
   }
 }
 return (
  <form ref={formRef} className="min-w-0 space-y-6" onSubmit={submit} noValidate>
   <label className="block text-sm font-semibold text-ink">{t('prints.form.name')}<input {...attrs('name')} className={input} value={v.name} onChange={e=>update({name:e.target.value})} required disabled={isSubmitting}/>{message('name')}</label>
   <fieldset className="space-y-4">
    <legend className="text-sm font-semibold text-ink">{t('prints.form.spools')}</legend>
    {v.spools.map((row,index)=>{
     const preview=previews.find(item=>item.key===row.key)
     const selected=preview?.spool
     const costText=preview?.cost&&selected?formatCurrency(preview.cost.materialCost,selected.currency):preview?.spool&&preview.hasValidWeight?t('prints.form.costUnavailable'):'—'
     return <div key={row.key} className="min-w-0 rounded-lg border border-line p-4">
      <div className="flex items-center justify-between"><strong>{t('prints.form.spoolNumber',{number:index+1})}</strong>{v.spools.length>1&&<button type="button" disabled={isSubmitting} onClick={()=>update({spools:v.spools.filter(r=>r.key!==row.key)})}>{t('prints.form.removeSpool')}</button>}</div>
      <label className="mt-3 block text-sm">{t('prints.form.spool')}<select {...attrs(`spools.${row.key}.spool_id`)} className={input} value={row.spoolId} onChange={e=>updateRow(row.key,{spoolId:e.target.value})} disabled={isSubmitting} required><option value="">{t('prints.form.selectSpool')}</option>{row.spoolId&&!selected&&<option value={row.spoolId}>{t('prints.spoolFallback',{id:row.spoolId})}</option>}{spools.filter(s=>s.status!=='ARCHIVED'||s.id===Number(row.spoolId)).map(s=><option disabled={chosen(String(s.id),row.key)} key={s.id} value={s.id}>{label(s)}</option>)}</select>{message(`spools.${row.key}.spool_id`)}</label>
      {selected&&<p className="mt-2 text-xs text-ink-muted">{selected.material.name} · {formatWeight(Number(selected.current_filament_weight_g))} · {formatPercent(selected.remaining_percent)} · {t(`status.${selected.status}`)}</p>}
      <label className="mt-3 block text-sm">{t('prints.form.estimatedWeight')}<input {...attrs(`spools.${row.key}.estimated_weight_g`)} className={input} min="0" step="any" type="number" value={row.estimatedWeight} onChange={e=>updateRow(row.key,{estimatedWeight:e.target.value})} disabled={isSubmitting}/>{message(`spools.${row.key}.estimated_weight_g`)}</label>
      <div className="mt-3 rounded-md bg-surface-raised px-3 py-2.5"><p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{t('prints.form.estimatedCost')}</p><p aria-live="polite" className="mt-1 font-mono text-base font-semibold text-ink" data-testid={`estimated-cost-${row.key}`}>{costText}</p></div>
     </div>
    })}
    <button type="button" className="rounded-md border border-line px-3 py-2 text-sm" disabled={isSubmitting} onClick={()=>{update({spools:[...v.spools,newRow(next)]});setNext(n=>n+1)}}>+ {t('prints.form.addSpool')}</button>
    <div aria-live="polite" className="rounded-lg border border-line bg-surface-raised p-4" data-testid="estimated-print-cost-summary"><p className="text-sm font-semibold text-ink">{t('prints.form.estimatedPrintCost')}</p>{totals.length===0?<p className="mt-2 font-mono text-lg font-semibold text-ink">—</p>:<dl className="mt-2 space-y-1">{totals.map(total=><div className="flex items-baseline justify-between gap-4" data-testid={`estimated-print-cost-${total.currency}`} key={total.currency}><dt className="font-mono text-xs font-semibold text-ink-muted">{total.currency}</dt><dd className="font-mono text-lg font-semibold text-ink">{formatCurrency(total.amount,total.currency)}</dd></div>)}</dl>}{unavailableCount>0&&<p className="mt-2 text-xs text-ink-muted">{t('prints.form.unavailableCostCount',{count:unavailableCount})}</p>}</div>
   </fieldset>
   <div className="grid gap-3 sm:grid-cols-2"><label>{t('prints.form.hours')}<input {...attrs('estimated_time_minutes')} className={input} min="0" type="number" value={v.hours} onChange={e=>update({hours:e.target.value})}/></label><label>{t('prints.form.minutes')}<input {...attrs('estimated_time_minutes')} id="print-minutes" className={input} min="0" max="59" type="number" value={v.minutes} onChange={e=>update({minutes:e.target.value})}/></label>{message('estimated_time_minutes')}</div>
   <label className="block">{t('prints.form.printer')}<input {...attrs('printer_name')} className={input} value={v.printerName} onChange={e=>update({printerName:e.target.value})}/>{message('printer_name')}</label>
   <label className="block">{t('prints.form.notes')}<textarea {...attrs('notes')} className={input} value={v.notes} onChange={e=>update({notes:e.target.value})}/>{message('notes')}</label>
   {errors.formError&&<div data-save-alert role="alert" tabIndex={-1} className="break-words rounded-lg border border-red-500/40 bg-surface p-4 text-sm text-red-700 dark:text-red-300"><p className="font-semibold">{t('prints.form.saveError')}</p><p className="mt-1">{errors.formError}</p></div>}
   <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><button type="button" onClick={onCancel} disabled={isSubmitting}>{t('prints.actions.cancel')}</button><button className="rounded-md bg-accent px-4 py-2 text-sidebar" disabled={isSubmitting} type="submit">{isSubmitting?t('prints.form.saving'):mode==='create'?t('prints.actions.create'):t('prints.actions.save')}</button></div>
  </form>
 )
}

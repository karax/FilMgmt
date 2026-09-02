from datetime import timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from app.models import PrintJob, PrintJobSpool, PrintJobStatus, PrintSpoolLock, Spool, SpoolStatus, WeightSource
from app.models.timestamps import utc_now
from app.schemas import PrintJobCreate, PrintJobFilterParams, PrintJobFinishRequest, PrintJobUpdate
from app.services.print_cost_service import InvalidPrintCostDataError, calculate_print_material_cost
from app.services.spool_status_service import release_spool_from_use
from app.services.spool_weight_service import apply_spool_weight_update

class PrintJobNotFoundError(Exception): pass
class PrintJobSpoolNotFoundError(Exception): pass
class PrintJobArchivedSpoolError(Exception): pass
class PrintJobDataConflictError(Exception): pass
class PrintJobNotPlannedError(Exception): pass
class PrintJobStartArchivedSpoolError(Exception): pass
class PrintJobStartEmptySpoolError(Exception): pass
class PrintJobSpoolInUseError(Exception): pass
class PrintJobActiveSpoolJobError(Exception): pass
class PrintJobNotPrintingError(Exception): pass
class PrintJobMissingStartTimeError(Exception): pass
class PrintJobInvalidFinishTimeError(Exception): pass
class PrintJobFinishArchivedSpoolError(Exception): pass
class PrintJobConsumptionExceedsWeightError(Exception): pass
class PrintJobInvalidCostDataError(Exception): pass

class PrintJobService:
 def __init__(self, db: Session): self.db = db
 def _query(self): return select(PrintJob).options(selectinload(PrintJob.spool_links))
 def list_print_jobs(self, filters: PrintJobFilterParams | None = None):
  filters = filters or PrintJobFilterParams(); q = self._query()
  if filters.status is not None: q = q.where(PrintJob.status == filters.status)
  if filters.spool_id is not None: q = q.join(PrintJobSpool).where(PrintJobSpool.spool_id == filters.spool_id)
  return list(self.db.scalars(q.order_by(PrintJob.created_at.desc(), PrintJob.id.desc())).unique().all())
 def get_print_job(self, id: int):
  item = self.db.scalar(self._query().where(PrintJob.id == id))
  if not item: raise PrintJobNotFoundError
  return item
 def _spools(self, entries):
  ids=[x.spool_id if hasattr(x, 'spool_id') else x['spool_id'] for x in entries]; found={x.id:x for x in self.db.scalars(select(Spool).where(Spool.id.in_(ids))).all()}
  if len(found)!=len(ids): raise PrintJobSpoolNotFoundError
  for s in found.values():
   if s.status is SpoolStatus.ARCHIVED or s.archived_at is not None: raise PrintJobArchivedSpoolError
  return found
 def _links(self, job, entries):
  return [PrintJobSpool(spool_id=x.spool_id if hasattr(x, 'spool_id') else x['spool_id'], position=i, estimated_weight_g=x.estimated_weight_g if hasattr(x, 'estimated_weight_g') else x.get('estimated_weight_g')) for i,x in enumerate(entries)]
 def create_print_job(self,payload):
  self._spools(payload.spools); data=payload.model_dump(exclude={'spools'}); job=PrintJob(**data); job.spool_links=self._links(job,payload.spools)
  try: self.db.add(job); self.db.commit()
  except IntegrityError as e: self.db.rollback(); raise PrintJobDataConflictError from e
  return self.get_print_job(job.id)
 def update_print_job(self,id,payload):
  job=self.get_print_job(id)
  if job.status is not PrintJobStatus.PLANNED: raise PrintJobNotPlannedError
  changes=payload.model_dump(exclude_unset=True)
  entries=changes.pop('spools',None)
  if entries is not None:
   self._spools(entries)
   job.spool_links.clear(); self.db.flush(); job.spool_links.extend(self._links(job,entries))
  for k,v in changes.items(): setattr(job,k,v)
  try: self.db.commit()
  except IntegrityError as e: self.db.rollback(); raise PrintJobDataConflictError from e
  return self.get_print_job(id)
 def start_print_job(self,id):
  job=self.get_print_job(id)
  if job.status is not PrintJobStatus.PLANNED: raise PrintJobNotPlannedError
  spools=self._spools(job.spool_links)
  for spool in spools.values():
   if spool.status is SpoolStatus.EMPTY: raise PrintJobStartEmptySpoolError
   if spool.status is SpoolStatus.IN_USE: raise PrintJobSpoolInUseError
   if self.db.get(PrintSpoolLock,spool.id): raise PrintJobActiveSpoolJobError
  now=utc_now()
  try:
   for spool in spools.values(): self.db.add(PrintSpoolLock(spool_id=spool.id,print_job_id=job.id)); spool.status=SpoolStatus.IN_USE; spool.opened_at=spool.opened_at or now; spool.last_used_at=now
   job.status=PrintJobStatus.PRINTING; job.started_at=now; self.db.commit()
  except IntegrityError as e: self.db.rollback(); raise PrintJobActiveSpoolJobError from e
  except SQLAlchemyError as e: self.db.rollback(); raise PrintJobDataConflictError from e
  return self.get_print_job(id)
 def finish_print_job(self,id,payload:PrintJobFinishRequest):
  job=self.get_print_job(id)
  if job.status is not PrintJobStatus.PRINTING: raise PrintJobNotPrintingError
  if job.started_at is None: raise PrintJobMissingStartTimeError
  links={x.spool_id:x for x in job.spool_links}; supplied={x.spool_id:x.actual_weight_g for x in payload.consumptions}
  if not set(supplied).issubset(links): raise PrintJobSpoolNotFoundError
  spools=self._spools(job.spool_links)
  locks={sid:self.db.get(PrintSpoolLock,sid) for sid in links}
  if any(lock is None or lock.print_job_id != id for lock in locks.values()): raise PrintJobDataConflictError
  if any(weight > spools[sid].current_filament_weight_g for sid,weight in supplied.items()): raise PrintJobConsumptionExceedsWeightError
  now=utc_now()
  started_at = job.started_at if job.started_at.tzinfo else job.started_at.replace(tzinfo=timezone.utc)
  if now < started_at: raise PrintJobInvalidFinishTimeError
  try:
   for sid,link in links.items():
    spool=spools[sid]
    if spool.status is SpoolStatus.ARCHIVED or spool.archived_at is not None: raise PrintJobFinishArchivedSpoolError
    weight=supplied.get(sid)
    if weight is not None:
     link.actual_weight_g=weight; cost=calculate_print_material_cost(spool.purchase_price,spool.initial_filament_weight_g,weight,spool.currency); link.filament_cost_per_g=cost.filament_cost_per_g; link.material_cost=cost.material_cost; link.material_cost_currency=cost.currency
     if weight > 0: apply_spool_weight_update(self.db,spool,spool.current_filament_weight_g-weight,WeightSource.PRINT,f'Print job #{job.id}: {job.name}')
    spool.last_used_at=now
    self.db.delete(locks[sid])
    release_spool_from_use(spool)
   job.status=PrintJobStatus.SUCCESS; job.finished_at=now; job.actual_time_minutes=int((now-started_at).total_seconds()//60); self.db.commit()
  except InvalidPrintCostDataError as e: self.db.rollback(); raise PrintJobInvalidCostDataError from e
  except SQLAlchemyError as e: self.db.rollback(); raise PrintJobDataConflictError from e
  return self.get_print_job(id)

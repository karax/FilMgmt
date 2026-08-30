from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import PrintJob, PrintJobStatus, Spool, SpoolStatus, WeightSource
from app.schemas import PrintJobCreate, PrintJobFilterParams, PrintJobFinishRequest, PrintJobUpdate
from app.models.timestamps import normalize_utc, utc_now
from app.services.spool_status_service import update_inventory_status
from app.services.spool_weight_service import apply_spool_weight_update
from app.services.print_cost_service import (
    InvalidPrintCostDataError,
    calculate_print_material_cost,
)


class PrintJobNotFoundError(Exception):
    pass


class PrintJobSpoolNotFoundError(Exception):
    pass


class PrintJobArchivedSpoolError(Exception):
    pass


class PrintJobNotPlannedError(Exception):
    pass


class PrintJobDataConflictError(Exception):
    pass


class PrintJobStartArchivedSpoolError(Exception):
    pass


class PrintJobStartEmptySpoolError(Exception):
    pass


class PrintJobSpoolInUseError(Exception):
    pass


class PrintJobActiveSpoolJobError(Exception):
    pass


class PrintJobNotPrintingError(Exception):
    pass


class PrintJobMissingStartTimeError(Exception):
    pass


class PrintJobInvalidFinishTimeError(Exception):
    pass


class PrintJobFinishArchivedSpoolError(Exception):
    pass


class PrintJobConsumptionExceedsWeightError(Exception):
    pass


class PrintJobInvalidCostDataError(Exception):
    pass


class PrintJobService:
    """Coordinate planning-only print job persistence and spool validation."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_print_jobs(self, filters: PrintJobFilterParams | None = None) -> list[PrintJob]:
        filters = filters or PrintJobFilterParams()
        statement = select(PrintJob)
        if filters.status is not None:
            statement = statement.where(PrintJob.status == filters.status)
        if filters.spool_id is not None:
            statement = statement.where(PrintJob.spool_id == filters.spool_id)
        statement = statement.order_by(PrintJob.created_at.desc(), PrintJob.id.desc())
        return list(self.db.scalars(statement).all())

    def get_print_job(self, print_job_id: int) -> PrintJob:
        print_job = self.db.get(PrintJob, print_job_id)
        if print_job is None:
            raise PrintJobNotFoundError
        return print_job

    def create_print_job(self, payload: PrintJobCreate) -> PrintJob:
        self._validate_spool(payload.spool_id)
        print_job = PrintJob(**payload.model_dump())
        try:
            self.db.add(print_job)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise PrintJobDataConflictError from error
        return self.get_print_job(print_job.id)

    def update_print_job(self, print_job_id: int, payload: PrintJobUpdate) -> PrintJob:
        print_job = self.get_print_job(print_job_id)
        if print_job.status is not PrintJobStatus.PLANNED:
            raise PrintJobNotPlannedError
        changes = payload.model_dump(exclude_unset=True)
        if "spool_id" in changes:
            self._validate_spool(changes["spool_id"])
        for field, value in changes.items():
            setattr(print_job, field, value)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise PrintJobDataConflictError from error
        return self.get_print_job(print_job_id)

    def start_print_job(self, print_job_id: int) -> PrintJob:
        """Atomically mark a planned job and its spool as actively in use."""
        print_job = self.get_print_job(print_job_id)
        if print_job.status is not PrintJobStatus.PLANNED:
            raise PrintJobNotPlannedError

        spool = self.db.get(Spool, print_job.spool_id)
        if spool is None:
            raise PrintJobSpoolNotFoundError
        if spool.status is SpoolStatus.ARCHIVED or spool.archived_at is not None:
            raise PrintJobStartArchivedSpoolError
        if spool.status is SpoolStatus.EMPTY:
            raise PrintJobStartEmptySpoolError
        if spool.status is SpoolStatus.IN_USE:
            raise PrintJobSpoolInUseError
        active_job_id = self.db.scalar(
            select(PrintJob.id)
            .where(
                PrintJob.spool_id == spool.id,
                PrintJob.status == PrintJobStatus.PRINTING,
                PrintJob.id != print_job.id,
            )
            .limit(1)
        )
        if active_job_id is not None:
            raise PrintJobActiveSpoolJobError

        now = utc_now()
        print_job.status = PrintJobStatus.PRINTING
        print_job.started_at = now
        spool.status = SpoolStatus.IN_USE
        if spool.opened_at is None:
            spool.opened_at = now
        spool.last_used_at = now
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            # The partial unique index is the final protection against a race
            # between concurrent start requests for the same spool.
            raise PrintJobActiveSpoolJobError from error
        except SQLAlchemyError as error:
            self.db.rollback()
            raise PrintJobDataConflictError from error
        return self.get_print_job(print_job_id)

    def finish_print_job(
        self,
        print_job_id: int,
        payload: PrintJobFinishRequest,
    ) -> PrintJob:
        """Atomically complete a running print without applying consumption."""
        print_job = self.get_print_job(print_job_id)
        if print_job.status is not PrintJobStatus.PRINTING:
            raise PrintJobNotPrintingError
        if print_job.started_at is None:
            raise PrintJobMissingStartTimeError
        spool = self.db.get(Spool, print_job.spool_id)
        if spool is None:
            raise PrintJobSpoolNotFoundError
        if spool.status is SpoolStatus.ARCHIVED or spool.archived_at is not None:
            raise PrintJobFinishArchivedSpoolError
        actual_weight = payload.actual_weight_g
        if (
            actual_weight is not None
            and actual_weight > spool.current_filament_weight_g
        ):
            raise PrintJobConsumptionExceedsWeightError

        started_at = normalize_utc(print_job.started_at)
        now = utc_now()
        if now < started_at:
            raise PrintJobInvalidFinishTimeError
        duration_minutes = int((now - started_at).total_seconds() // 60)
        print_job.status = PrintJobStatus.SUCCESS
        print_job.finished_at = now
        print_job.actual_time_minutes = duration_minutes
        if actual_weight is not None:
            print_job.actual_weight_g = actual_weight
        try:
            cost = calculate_print_material_cost(
                spool.purchase_price,
                spool.initial_filament_weight_g,
                actual_weight,
                spool.currency,
            )
        except InvalidPrintCostDataError as error:
            self.db.rollback()
            raise PrintJobInvalidCostDataError from error
        print_job.filament_cost_per_g = cost.filament_cost_per_g
        print_job.material_cost = cost.material_cost
        print_job.material_cost_currency = cost.currency
        # Force a normal inventory evaluation instead of preserving IN_USE.
        spool.status = SpoolStatus.OPEN
        if actual_weight is not None and actual_weight > Decimal("0"):
            apply_spool_weight_update(
                self.db,
                spool,
                spool.current_filament_weight_g - actual_weight,
                WeightSource.PRINT,
                f"Print job #{print_job.id}: {print_job.name}",
            )
        else:
            update_inventory_status(spool)
        spool.last_used_at = now
        try:
            self.db.commit()
        except SQLAlchemyError as error:
            self.db.rollback()
            raise PrintJobDataConflictError from error
        return self.get_print_job(print_job_id)

    def _validate_spool(self, spool_id: int) -> Spool:
        spool = self.db.get(Spool, spool_id)
        if spool is None:
            raise PrintJobSpoolNotFoundError
        if spool.status is SpoolStatus.ARCHIVED or spool.archived_at is not None:
            raise PrintJobArchivedSpoolError
        return spool

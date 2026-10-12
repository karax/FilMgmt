from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CalibrationEventType,
    PrintJob,
    PrintJobEnrichmentStatus,
    PrintJobFilamentUsage,
    PrintJobReconciliationStatus,
    Spool,
    SpoolCalibration,
    SpoolStatus,
    TareConfidence,
    TareMeasurement,
    TareProfile,
    TareSource,
    WeightSource,
)
from app.models.timestamps import utc_now
from app.schemas.calibration import (
    CalibrationConfirmRequest,
    CalibrationInput,
    CalibrationPreviewRead,
    CalibrationRead,
    CalibrationUndoRequest,
    EmptySpoolMeasurementCreate,
    EmptySpoolMeasurementRead,
    PendingPrintWarning,
    TareProfileCreate,
    TareProfileRead,
    TareProfileUpdate,
)
from app.services.spool_weight_service import SpoolWeightOutOfRangeError, apply_spool_weight_update


_WEIGHT_QUANTUM = Decimal("0.001")
_OPEN_RECONCILIATION_STATUSES = {
    PrintJobReconciliationStatus.PENDING,
    PrintJobReconciliationStatus.PARTIALLY_RECONCILED,
    PrintJobReconciliationStatus.NEEDS_REVIEW,
}


class CalibrationNotFoundError(Exception):
    pass


class CalibrationConflictError(Exception):
    pass


class CalibrationValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class CalibrationStalePreviewError(Exception):
    def __init__(self, preview: CalibrationPreviewRead) -> None:
        self.preview = preview


class TareProfileNotFoundError(Exception):
    pass


class TareProfileConflictError(Exception):
    pass


@dataclass(frozen=True)
class _ResolvedTare:
    tare_g: Decimal
    source: TareSource
    confidence: TareConfidence
    profile: TareProfile | None


def default_confidence(source: TareSource) -> TareConfidence:
    return {
        TareSource.MEASURED: TareConfidence.HIGH,
        TareSource.KNOWN: TareConfidence.HIGH,
        TareSource.ESTIMATED: TareConfidence.LOW,
        TareSource.MANUAL: TareConfidence.MEDIUM,
    }[source]


class CalibrationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def preview(self, code: str, payload: CalibrationInput) -> CalibrationPreviewRead:
        spool = self._spool(code)
        tare = self._resolve_tare(payload)
        return self._build_preview(spool, payload.measured_total_g, tare)

    def confirm(self, code: str, payload: CalibrationConfirmRequest) -> CalibrationRead:
        self._begin_immediate()
        spool = self._spool(code)
        tare = self._resolve_tare(payload)
        measured = self._weight(payload.measured_total_g)

        existing = self.db.scalar(
            select(SpoolCalibration)
            .where(SpoolCalibration.idempotency_key == payload.idempotency_key)
            .options(selectinload(SpoolCalibration.tare_profile))
        )
        if existing is not None:
            if (
                existing.spool_id != spool.id
                or existing.measured_total_g != measured
                or existing.tare_g_used != tare.tare_g
                or existing.tare_source_used is not tare.source
                or existing.tare_confidence_used is not tare.confidence
                or existing.tare_profile_id != (tare.profile.id if tare.profile else None)
            ):
                self.db.rollback()
                raise CalibrationConflictError
            self.db.rollback()
            return self._read(existing)

        current = self._weight(spool.current_filament_weight_g)
        if current != self._weight(payload.expected_current_remaining_g):
            preview = self._build_preview(spool, measured, tare)
            self.db.rollback()
            raise CalibrationStalePreviewError(preview)

        preview = self._build_preview(spool, measured, tare)
        now = utc_now()
        event = SpoolCalibration(
            spool_id=spool.id,
            event_type=CalibrationEventType.PHYSICAL_CALIBRATION,
            measured_total_g=preview.measured_total_g,
            tare_g_used=preview.tare_g,
            calculated_filament_g=preview.calculated_filament_g,
            previous_remaining_g=preview.current_remaining_g,
            adjustment_g=preview.adjustment_g,
            new_remaining_g=preview.calculated_filament_g,
            tare_source_used=preview.tare_source,
            tare_confidence_used=preview.tare_confidence,
            tare_profile_id=preview.tare_profile_id,
            note=payload.note,
            idempotency_key=payload.idempotency_key,
            effective_at=now,
        )
        try:
            apply_spool_weight_update(
                self.db,
                spool,
                preview.calculated_filament_g,
                WeightSource.SCALE,
                f"Physical calibration ({preview.adjustment_g:+.3f} g)",
            )
            if spool.status is SpoolStatus.SEALED and preview.calculated_filament_g > 0:
                spool.status = SpoolStatus.OPEN
                spool.opened_at = spool.opened_at or now
            self.db.add(event)
            self.db.commit()
        except (IntegrityError, SQLAlchemyError, SpoolWeightOutOfRangeError) as error:
            self.db.rollback()
            if isinstance(error, SpoolWeightOutOfRangeError):
                raise CalibrationValidationError(
                    "Physical filament must be within this spool's inventory capacity."
                ) from error
            raise CalibrationConflictError from error
        self.db.refresh(event)
        if event.tare_profile_id is not None:
            event.tare_profile = tare.profile
        return self._read(event)

    def list_calibrations(self, code: str) -> list[CalibrationRead]:
        spool = self._spool(code)
        events = self.db.scalars(
            select(SpoolCalibration)
            .where(SpoolCalibration.spool_id == spool.id)
            .options(selectinload(SpoolCalibration.tare_profile))
            .order_by(SpoolCalibration.created_at.desc(), SpoolCalibration.id.desc())
        ).all()
        return [self._read(event) for event in events]

    def undo(
        self, code: str, calibration_id: int, payload: CalibrationUndoRequest
    ) -> CalibrationRead:
        self._begin_immediate()
        spool = self._spool(code)
        calibration = self.db.scalar(
            select(SpoolCalibration).where(
                SpoolCalibration.id == calibration_id,
                SpoolCalibration.spool_id == spool.id,
                SpoolCalibration.event_type == CalibrationEventType.PHYSICAL_CALIBRATION,
            )
        )
        if calibration is None:
            self.db.rollback()
            raise CalibrationNotFoundError
        if calibration.reversed_at is not None:
            reversal = self.db.scalar(
                select(SpoolCalibration).where(
                    SpoolCalibration.reversed_calibration_id == calibration.id
                )
            )
            self.db.rollback()
            if reversal is None:
                raise CalibrationConflictError
            return self._read(reversal)

        current = self._weight(spool.current_filament_weight_g)
        if current != calibration.new_remaining_g:
            self.db.rollback()
            raise CalibrationConflictError

        now = utc_now()
        reversal = SpoolCalibration(
            spool_id=spool.id,
            event_type=CalibrationEventType.REVERSAL,
            previous_remaining_g=current,
            adjustment_g=calibration.previous_remaining_g - current,
            new_remaining_g=calibration.previous_remaining_g,
            note=payload.reason,
            reversed_calibration_id=calibration.id,
            effective_at=now,
        )
        try:
            apply_spool_weight_update(
                self.db,
                spool,
                calibration.previous_remaining_g,
                WeightSource.CORRECTION,
                f"Undo physical calibration #{calibration.id}: {payload.reason}",
            )
            calibration.reversed_at = now
            self.db.add(reversal)
            self.db.commit()
        except (IntegrityError, SQLAlchemyError, SpoolWeightOutOfRangeError) as error:
            self.db.rollback()
            raise CalibrationConflictError from error
        self.db.refresh(reversal)
        return self._read(reversal)

    def record_empty_spool(
        self, code: str, payload: EmptySpoolMeasurementCreate
    ) -> EmptySpoolMeasurementRead:
        self._begin_immediate()
        spool = self._spool(code)
        profile = None
        if payload.tare_profile_id is not None:
            profile = self.db.get(TareProfile, payload.tare_profile_id)
            if profile is None or profile.archived_at is not None:
                self.db.rollback()
                raise TareProfileNotFoundError
        measured = self._weight(payload.measured_tare_g)
        row = TareMeasurement(
            spool_id=spool.id,
            tare_profile_id=profile.id if profile else None,
            measured_tare_g=measured,
            contributes_to_profile=payload.contribute_to_profile,
            note=payload.note,
        )
        try:
            spool.empty_spool_weight_g = measured
            self.db.add(row)
            self.db.flush()
            if profile is not None and payload.contribute_to_profile:
                self._refresh_profile_measurements(profile)
            self.db.commit()
        except (IntegrityError, SQLAlchemyError) as error:
            self.db.rollback()
            raise CalibrationConflictError from error
        self.db.refresh(row)
        return EmptySpoolMeasurementRead.model_validate(row)

    def _build_preview(
        self, spool: Spool, measured_total_g: Decimal, tare: _ResolvedTare
    ) -> CalibrationPreviewRead:
        measured = self._weight(measured_total_g)
        calculated = measured - tare.tare_g
        if calculated < 0:
            raise CalibrationValidationError(
                "Empty spool weight cannot exceed the measured total weight."
            )
        calculated = self._weight(calculated)
        if calculated > self._weight(spool.initial_filament_weight_g):
            raise CalibrationValidationError(
                "Physical filament cannot exceed this spool's initial filament weight."
            )
        current = self._weight(spool.current_filament_weight_g)
        return CalibrationPreviewRead(
            measured_total_g=measured,
            tare_g=tare.tare_g,
            calculated_filament_g=calculated,
            current_remaining_g=current,
            adjustment_g=calculated - current,
            tare_source=tare.source,
            tare_confidence=tare.confidence,
            tare_profile_id=tare.profile.id if tare.profile else None,
            is_estimated=tare.source is TareSource.ESTIMATED,
            unreconciled_prints=self._pending_print_warnings(spool),
        )

    def _pending_print_warnings(self, spool: Spool) -> list[PendingPrintWarning]:
        jobs = self.db.scalars(
            select(PrintJob)
            .where(
                PrintJob.enrichment_status == PrintJobEnrichmentStatus.ENRICHED,
                PrintJob.reconciliation_status.in_(_OPEN_RECONCILIATION_STATUSES),
                PrintJob.filament_usages.any(),
            )
            .options(
                selectinload(PrintJob.filament_usages).selectinload(
                    PrintJobFilamentUsage.reconciliation_events
                )
            )
            .order_by(PrintJob.finished_at.desc(), PrintJob.id.desc())
        ).unique().all()
        material = _normalize(spool.material.name)
        warnings = []
        for job in jobs:
            if any(
                usage.current_reconciliation is None
                and _normalize(usage.material_type) == material
                for usage in job.filament_usages
            ):
                warnings.append(
                    PendingPrintWarning(
                        print_job_id=job.id,
                        name=job.name,
                        printed_at=job.finished_at or job.started_at,
                    )
                )
        return warnings

    def _resolve_tare(self, payload: CalibrationInput) -> _ResolvedTare:
        if payload.tare_profile_id is not None:
            profile = self.db.get(TareProfile, payload.tare_profile_id)
            if profile is None or profile.archived_at is not None:
                raise TareProfileNotFoundError
            return _ResolvedTare(
                self._weight(profile.tare_g), profile.source, profile.confidence, profile
            )
        assert payload.tare_g is not None and payload.tare_source is not None
        return _ResolvedTare(
            self._weight(payload.tare_g),
            payload.tare_source,
            payload.tare_confidence or default_confidence(payload.tare_source),
            None,
        )

    def _spool(self, code: str) -> Spool:
        spool = self.db.scalar(
            select(Spool)
            .where(Spool.code == code.strip().upper())
            .options(selectinload(Spool.material))
        )
        if spool is None:
            raise CalibrationNotFoundError
        if spool.archived_at is not None or spool.status is SpoolStatus.ARCHIVED:
            raise CalibrationConflictError
        return spool

    def _refresh_profile_measurements(self, profile: TareProfile) -> None:
        count, average, minimum, maximum = self.db.execute(
            select(
                func.count(TareMeasurement.id),
                func.avg(TareMeasurement.measured_tare_g),
                func.min(TareMeasurement.measured_tare_g),
                func.max(TareMeasurement.measured_tare_g),
            ).where(
                TareMeasurement.tare_profile_id == profile.id,
                TareMeasurement.contributes_to_profile.is_(True),
            )
        ).one()
        profile.measured_sample_count = int(count)
        profile.tare_g = self._weight(Decimal(str(average)))
        profile.measured_min_g = self._weight(Decimal(str(minimum)))
        profile.measured_max_g = self._weight(Decimal(str(maximum)))
        profile.source = TareSource.MEASURED
        profile.confidence = TareConfidence.HIGH

    @staticmethod
    def _weight(value: Decimal) -> Decimal:
        return Decimal(value).quantize(_WEIGHT_QUANTUM)

    @staticmethod
    def _read(event: SpoolCalibration) -> CalibrationRead:
        return CalibrationRead(
            id=event.id,
            spool_id=event.spool_id,
            event_type=event.event_type,
            measured_total_g=event.measured_total_g,
            tare_g_used=event.tare_g_used,
            calculated_filament_g=event.calculated_filament_g,
            previous_remaining_g=event.previous_remaining_g,
            adjustment_g=event.adjustment_g,
            new_remaining_g=event.new_remaining_g,
            tare_source_used=event.tare_source_used,
            tare_confidence_used=event.tare_confidence_used,
            tare_profile_id=event.tare_profile_id,
            tare_profile_name=(event.tare_profile.name if event.tare_profile else None),
            note=event.note,
            reversed_calibration_id=event.reversed_calibration_id,
            reversed_at=event.reversed_at,
            effective_at=event.effective_at,
            created_at=event.created_at,
        )

    def _begin_immediate(self) -> None:
        bind = self.db.get_bind()
        if bind.dialect.name == "sqlite" and not self.db.in_transaction():
            try:
                self.db.execute(text("BEGIN IMMEDIATE"))
            except SQLAlchemyError as error:
                self.db.rollback()
                raise CalibrationConflictError from error


class TareProfileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, include_archived: bool = False) -> list[TareProfileRead]:
        statement = select(TareProfile)
        if not include_archived:
            statement = statement.where(TareProfile.archived_at.is_(None))
        rows = self.db.scalars(statement.order_by(TareProfile.name, TareProfile.id)).all()
        return [TareProfileRead.model_validate(row) for row in rows]

    def create(self, payload: TareProfileCreate) -> TareProfileRead:
        profile = TareProfile(
            **payload.model_dump(exclude={"confidence"}),
            confidence=payload.confidence or default_confidence(payload.source),
        )
        try:
            self.db.add(profile)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise TareProfileConflictError from error
        self.db.refresh(profile)
        return TareProfileRead.model_validate(profile)

    def update(self, profile_id: int, payload: TareProfileUpdate) -> TareProfileRead:
        profile = self.db.get(TareProfile, profile_id)
        if profile is None:
            raise TareProfileNotFoundError
        changes = payload.model_dump(exclude_unset=True, exclude={"archived"})
        for key, value in changes.items():
            setattr(profile, key, value)
        if "source" in changes and "confidence" not in changes:
            profile.confidence = default_confidence(profile.source)
        if payload.archived is True:
            profile.archived_at = utc_now()
        elif payload.archived is False:
            profile.archived_at = None
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise TareProfileConflictError from error
        self.db.refresh(profile)
        return TareProfileRead.model_validate(profile)

    def delete(self, profile_id: int) -> None:
        profile = self.db.get(TareProfile, profile_id)
        if profile is None:
            raise TareProfileNotFoundError
        used = self.db.scalar(
            select(func.count()).select_from(SpoolCalibration).where(
                SpoolCalibration.tare_profile_id == profile.id
            )
        ) or self.db.scalar(
            select(func.count()).select_from(TareMeasurement).where(
                TareMeasurement.tare_profile_id == profile.id
            )
        )
        if used:
            raise TareProfileConflictError
        self.db.delete(profile)
        self.db.commit()


def _normalize(value: object | None) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())

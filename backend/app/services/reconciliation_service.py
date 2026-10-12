from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import re

from sqlalchemy import Select, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    FilamentReconciliationEventType,
    PrintJob,
    PrintJobEnrichmentStatus,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    PrintJobReconciliationStatus,
    PrintJobStatus,
    Spool,
    CalibrationEventType,
    SpoolStatus,
    WeightSource,
)
from app.models.timestamps import utc_now
from app.schemas.reconciliation import (
    CandidateConfidence,
    ReconciliationAction,
    ReconciliationCandidateReason,
    ReconciliationConfirmRequest,
    ReconciliationConfirmResult,
    ReconciliationJobRead,
    ReconciliationQueueRead,
    ReconciliationResolutionRead,
    ReconciliationSpoolCandidate,
    ReconciliationSpoolOption,
    ReconciliationUndoRequest,
    ReconciliationUsageRead,
)
from app.services.spool_weight_service import (
    SpoolWeightOutOfRangeError,
    apply_spool_weight_update,
)


_TERMINAL_STATUSES = {
    PrintJobStatus.SUCCESS,
    PrintJobStatus.COMPLETED,
    PrintJobStatus.FAILED,
    PrintJobStatus.CANCELLED,
    PrintJobStatus.UNKNOWN_TERMINAL,
}
_INCOMPLETE_STATUSES = {
    PrintJobStatus.FAILED,
    PrintJobStatus.CANCELLED,
    PrintJobStatus.UNKNOWN_TERMINAL,
}
_OPEN_RECONCILIATION_STATUSES = {
    PrintJobReconciliationStatus.PENDING,
    PrintJobReconciliationStatus.PARTIALLY_RECONCILED,
    PrintJobReconciliationStatus.NEEDS_REVIEW,
}
_WEIGHT_QUANTUM = Decimal("0.001")


class ReconciliationNotFoundError(Exception):
    pass


class ReconciliationConflictError(Exception):
    pass


class ReconciliationInsufficientWeightError(Exception):
    def __init__(self, spool_id: int) -> None:
        self.spool_id = spool_id


class ReconciliationManualReasonRequiredError(Exception):
    pass


class ReconciliationInvalidSpoolError(Exception):
    def __init__(self, spool_id: int) -> None:
        self.spool_id = spool_id


class ReconciliationCheckpointAcknowledgementRequiredError(Exception):
    def __init__(self, spool_id: int, calibration_at: datetime) -> None:
        self.spool_id = spool_id
        self.calibration_at = calibration_at


@dataclass(frozen=True)
class _TrayEvidence:
    label: str
    material: str | None
    color: str | None
    brand: str | None
    profile_id: str | None
    setting_id: str | None
    tag_uid: str | None
    tray_uuid: str | None

    @property
    def fingerprint(self) -> str:
        values = (
            self.label,
            self.material,
            self.color,
            self.brand,
            self.profile_id,
            self.setting_id,
            self.tag_uid,
            self.tray_uuid,
        )
        return "|".join(_normalize(value) for value in values)


@dataclass
class _RankedCandidate:
    spool: Spool
    score: int
    confidence: CandidateConfidence
    reasons: list[ReconciliationCandidateReason]
    sufficient: bool


class ReconciliationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_pending(self) -> ReconciliationQueueRead:
        jobs = list(self.db.scalars(self._eligible_query()).unique().all())
        recent_jobs = list(self.db.scalars(self._recent_query()).unique().all())
        spools = self._candidate_spools()
        history = self._active_consumption_history()
        reads = [self._build_job(job, spools, history) for job in jobs]
        recent_reads = [self._build_job(job, spools, history) for job in recent_jobs]

        pending_total = sum(
            (
                _progress_estimated_consumption(job, usage) or Decimal("0")
                for job in jobs
                for usage in job.filament_usages
                if usage.current_reconciliation is None
            ),
            Decimal("0"),
        )
        ready = sum(
            1
            for job in reads
            if job.status not in _INCOMPLETE_STATUSES
            and any(item.resolution is None for item in job.filaments)
            and all(
                item.resolution is not None or item.unambiguous
                for item in job.filaments
            )
        )
        return ReconciliationQueueRead(
            jobs=reads,
            recently_reconciled_jobs=recent_reads,
            available_spools=[
                ReconciliationSpoolOption(
                    id=spool.id,
                    code=spool.code,
                    display_name=spool.display_name,
                    manufacturer_name=spool.manufacturer.name,
                    material_name=spool.material.name,
                    color_name=spool.color_name,
                    color_hex=spool.color_hex,
                    current_filament_weight_g=spool.current_filament_weight_g,
                    latest_physical_calibration_at=_latest_checkpoint(spool),
                )
                for spool in spools
            ],
            pending_job_count=len(reads),
            ready_job_count=ready,
            needs_review_job_count=len(reads) - ready,
            estimated_pending_g=pending_total.quantize(_WEIGHT_QUANTUM),
        )

    def confirm(self, payload: ReconciliationConfirmRequest) -> ReconciliationConfirmResult:
        self._begin_immediate()
        usage_ids = [item.filament_usage_id for item in payload.items]
        usages = {
            usage.id: usage
            for usage in self.db.scalars(
                select(PrintJobFilamentUsage)
                .where(PrintJobFilamentUsage.id.in_(usage_ids))
                .options(
                    selectinload(PrintJobFilamentUsage.reconciliation_events).selectinload(
                        PrintJobFilamentReconciliation.spool
                    ),
                    selectinload(PrintJobFilamentUsage.print_job)
                    .selectinload(PrintJob.filament_usages)
                    .selectinload(PrintJobFilamentUsage.reconciliation_events),
                )
            ).unique().all()
        }
        if len(usages) != len(usage_ids):
            raise ReconciliationNotFoundError

        spools: dict[int, Spool] = {}
        pending_items = []
        totals: dict[int, Decimal] = {}
        affected_jobs: dict[int, PrintJob] = {}

        for item in payload.items:
            usage = usages[item.filament_usage_id]
            job = usage.print_job
            self._validate_eligible(job)
            affected_jobs[job.id] = job
            active = usage.current_reconciliation
            if active is not None:
                if self._same_resolution(active, item):
                    continue
                raise ReconciliationConflictError

            if item.action is ReconciliationAction.SKIP:
                pending_items.append((usage, item, None))
                continue

            assert item.spool_id is not None and item.consumption_g is not None
            spool = spools.get(item.spool_id) or self.db.get(Spool, item.spool_id)
            if spool is None:
                raise ReconciliationInvalidSpoolError(item.spool_id)
            if (
                spool.archived_at is not None
                or spool.status in {SpoolStatus.ARCHIVED, SpoolStatus.EMPTY}
            ):
                raise ReconciliationInvalidSpoolError(item.spool_id)
            spools[spool.id] = spool
            checkpoint_at = _latest_checkpoint(spool)
            printed_at = job.finished_at or job.started_at or job.created_at
            if (
                checkpoint_at is not None
                and _comparable_datetime(printed_at) <= _comparable_datetime(checkpoint_at)
                and not item.checkpoint_acknowledged
            ):
                raise ReconciliationCheckpointAcknowledgementRequiredError(
                    spool.id, checkpoint_at
                )
            amount = item.consumption_g.quantize(_WEIGHT_QUANTUM)
            manual = job.status in _INCOMPLETE_STATUSES or (
                usage.used_g is None
                or amount != Decimal(usage.used_g).quantize(_WEIGHT_QUANTUM)
            )
            if manual and item.reason is None:
                raise ReconciliationManualReasonRequiredError
            totals[spool.id] = totals.get(spool.id, Decimal("0")) + amount
            pending_items.append((usage, item, spool))

        for spool_id, total in totals.items():
            if total > spools[spool_id].current_filament_weight_g:
                raise ReconciliationInsufficientWeightError(spool_id)

        now = utc_now()
        reconciled_usage_ids: list[int] = []
        try:
            for usage, item, spool in pending_items:
                if item.action is ReconciliationAction.SKIP:
                    event = PrintJobFilamentReconciliation(
                        print_job_id=usage.print_job_id,
                        filament_usage_id=usage.id,
                        event_type=FilamentReconciliationEventType.SKIP,
                        amount_g=Decimal("0"),
                        sliced_estimated_g=usage.used_g,
                        manual_override=False,
                        reason=item.reason,
                    )
                else:
                    assert spool is not None and item.consumption_g is not None
                    amount = item.consumption_g.quantize(_WEIGHT_QUANTUM)
                    before = Decimal(spool.current_filament_weight_g).quantize(_WEIGHT_QUANTUM)
                    after = before - amount
                    manual = usage.print_job.status in _INCOMPLETE_STATUSES or (
                        usage.used_g is None
                        or amount != Decimal(usage.used_g).quantize(_WEIGHT_QUANTUM)
                    )
                    if spool.status is SpoolStatus.SEALED:
                        spool.status = SpoolStatus.OPEN
                    spool.opened_at = spool.opened_at or now
                    apply_spool_weight_update(
                        self.db,
                        spool,
                        after,
                        WeightSource.PRINT,
                        f"P1S reconciliation: print #{usage.print_job_id}, usage #{usage.id}",
                    )
                    spool.last_used_at = now
                    event = PrintJobFilamentReconciliation(
                        print_job_id=usage.print_job_id,
                        filament_usage_id=usage.id,
                        spool_id=spool.id,
                        event_type=FilamentReconciliationEventType.CONSUMPTION,
                        amount_g=amount,
                        sliced_estimated_g=usage.used_g,
                        remaining_before_g=before,
                        remaining_after_g=after,
                        manual_override=manual,
                        reason=item.reason,
                    )
                self.db.add(event)
                usage.reconciliation_events.append(event)
                reconciled_usage_ids.append(usage.id)

            self.db.flush()
            for job in affected_jobs.values():
                self._set_job_status(job)
            self.db.commit()
        except (IntegrityError, SQLAlchemyError, SpoolWeightOutOfRangeError) as error:
            self.db.rollback()
            raise ReconciliationConflictError from error

        reads = [self._reload_job(job_id) for job_id in sorted(affected_jobs)]
        return ReconciliationConfirmResult(
            reconciled_usage_ids=reconciled_usage_ids,
            print_jobs=reads,
        )

    def undo(
        self,
        filament_usage_id: int,
        payload: ReconciliationUndoRequest,
    ) -> ReconciliationJobRead:
        self._begin_immediate()
        usage = self.db.scalar(
            select(PrintJobFilamentUsage)
            .where(PrintJobFilamentUsage.id == filament_usage_id)
            .options(
                selectinload(PrintJobFilamentUsage.reconciliation_events).selectinload(
                    PrintJobFilamentReconciliation.spool
                ),
                selectinload(PrintJobFilamentUsage.print_job)
                .selectinload(PrintJob.filament_usages)
                .selectinload(PrintJobFilamentUsage.reconciliation_events),
            )
        )
        if usage is None:
            raise ReconciliationNotFoundError
        active = usage.current_reconciliation
        if active is None:
            # Retry-safe: a second undo observes the already-pending usage.
            self.db.rollback()
            return self._reload_job(usage.print_job_id)

        now = utc_now()
        before = after = None
        try:
            if active.event_type is FilamentReconciliationEventType.CONSUMPTION:
                spool = active.spool
                if spool is None:
                    raise ReconciliationConflictError
                before = Decimal(spool.current_filament_weight_g).quantize(_WEIGHT_QUANTUM)
                after = before + active.amount_g
                apply_spool_weight_update(
                    self.db,
                    spool,
                    after,
                    WeightSource.CORRECTION,
                    f"Undo P1S reconciliation #{active.id}: {payload.reason}",
                )

            active.reversed_at = now
            reversal = PrintJobFilamentReconciliation(
                print_job_id=usage.print_job_id,
                filament_usage_id=usage.id,
                spool_id=active.spool_id,
                event_type=FilamentReconciliationEventType.REVERSAL,
                amount_g=active.amount_g,
                sliced_estimated_g=active.sliced_estimated_g,
                remaining_before_g=before,
                remaining_after_g=after,
                manual_override=active.manual_override,
                reason=payload.reason,
                reversed_event_id=active.id,
            )
            self.db.add(reversal)
            usage.reconciliation_events.append(reversal)
            self.db.flush()
            self._set_job_status(usage.print_job)
            self.db.commit()
        except (IntegrityError, SQLAlchemyError, SpoolWeightOutOfRangeError) as error:
            self.db.rollback()
            raise ReconciliationConflictError from error
        return self._reload_job(usage.print_job_id)

    def _eligible_query(self) -> Select[tuple[PrintJob]]:
        return (
            select(PrintJob)
            .where(
                PrintJob.status.in_(_TERMINAL_STATUSES),
                PrintJob.enrichment_status == PrintJobEnrichmentStatus.ENRICHED,
                PrintJob.filament_usages.any(),
                (
                    PrintJob.reconciliation_status.is_(None)
                    | PrintJob.reconciliation_status.in_(_OPEN_RECONCILIATION_STATUSES)
                ),
            )
            .options(
                selectinload(PrintJob.filament_usages)
                .selectinload(PrintJobFilamentUsage.reconciliation_events)
                .selectinload(PrintJobFilamentReconciliation.spool)
            )
            .order_by(
                PrintJob.finished_at.desc(),
                PrintJob.created_at.desc(),
                PrintJob.id.desc(),
            )
        )

    def _candidate_spools(self) -> list[Spool]:
        return list(
            self.db.scalars(
                select(Spool)
                .where(
                    Spool.archived_at.is_(None),
                    Spool.status.not_in({SpoolStatus.ARCHIVED, SpoolStatus.EMPTY}),
                    Spool.current_filament_weight_g > 0,
                )
                .options(selectinload(Spool.manufacturer), selectinload(Spool.material))
                .options(selectinload(Spool.calibrations))
                .order_by(Spool.last_used_at.desc(), Spool.id)
            ).all()
        )

    def _recent_query(self) -> Select[tuple[PrintJob]]:
        return (
            select(PrintJob)
            .where(
                PrintJob.enrichment_status == PrintJobEnrichmentStatus.ENRICHED,
                PrintJob.filament_usages.any(),
                PrintJob.reconciliation_status.in_(
                    {
                        PrintJobReconciliationStatus.RECONCILED,
                        PrintJobReconciliationStatus.NOT_APPLICABLE,
                    }
                ),
            )
            .options(
                selectinload(PrintJob.filament_usages)
                .selectinload(PrintJobFilamentUsage.reconciliation_events)
                .selectinload(PrintJobFilamentReconciliation.spool)
            )
            .order_by(
                PrintJob.finished_at.desc(),
                PrintJob.created_at.desc(),
                PrintJob.id.desc(),
            )
            .limit(20)
        )

    def _active_consumption_history(self) -> list[PrintJobFilamentReconciliation]:
        return list(
            self.db.scalars(
                select(PrintJobFilamentReconciliation)
                .where(
                    PrintJobFilamentReconciliation.event_type
                    == FilamentReconciliationEventType.CONSUMPTION,
                    PrintJobFilamentReconciliation.reversed_at.is_(None),
                )
                .options(
                    selectinload(PrintJobFilamentReconciliation.print_job),
                    selectinload(PrintJobFilamentReconciliation.filament_usage),
                )
                .order_by(PrintJobFilamentReconciliation.created_at.desc())
            ).all()
        )

    def _build_job(
        self,
        job: PrintJob,
        spools: list[Spool],
        history: list[PrintJobFilamentReconciliation],
    ) -> ReconciliationJobRead:
        status = self._derived_job_status(job)
        usages = [
            self._build_usage(job, usage, spools, history)
            for usage in job.filament_usages
        ]
        return ReconciliationJobRead(
            id=job.id,
            name=job.name,
            gcode_file=job.gcode_file,
            status=job.status,
            reconciliation_status=status,
            started_at=job.started_at,
            finished_at=job.finished_at,
            duration_seconds=job.duration_seconds,
            actual_time_minutes=job.actual_time_minutes,
            final_progress=job.final_progress,
            selected_plate_index=job.selected_plate_index,
            selected_plate_name=job.selected_plate_name,
            thumbnail_url=job.thumbnail_url,
            filament_count=job.filament_count,
            estimated_filament_g=job.estimated_filament_g,
            filaments=usages,
        )

    def _build_usage(
        self,
        job: PrintJob,
        usage: PrintJobFilamentUsage,
        spools: list[Spool],
        history: list[PrintJobFilamentReconciliation],
    ) -> ReconciliationUsageRead:
        tray = _tray_evidence(job.ams_snapshot, usage)
        ranked = self._rank_candidates(job, usage, tray, spools, history)
        top_score = ranked[0].score if ranked else None
        top = [candidate for candidate in ranked if candidate.score == top_score]
        top_is_tied = len(top) > 1
        candidates: list[ReconciliationSpoolCandidate] = []
        for ranked_candidate in ranked:
            confidence = (
                CandidateConfidence.AMBIGUOUS
                if top_is_tied and ranked_candidate.score == top_score
                else ranked_candidate.confidence
            )
            spool = ranked_candidate.spool
            candidates.append(
                ReconciliationSpoolCandidate(
                    id=spool.id,
                    code=spool.code,
                    display_name=spool.display_name,
                    product_name=spool.product_name,
                    manufacturer_name=spool.manufacturer.name,
                    material_name=spool.material.name,
                    color_name=spool.color_name,
                    color_hex=spool.color_hex,
                    current_filament_weight_g=spool.current_filament_weight_g,
                    purchase_price=spool.purchase_price,
                    currency=spool.currency,
                    confidence=confidence,
                    reasons=ranked_candidate.reasons,
                    sufficient_remaining=ranked_candidate.sufficient,
                    latest_physical_calibration_at=_latest_checkpoint(spool),
                )
            )
        unambiguous = bool(
            len(top) == 1
            and top[0].confidence in {CandidateConfidence.HIGH, CandidateConfidence.EXACT}
            and top[0].sufficient
        )
        active = usage.current_reconciliation
        resolution = None
        if active is not None:
            resolution = ReconciliationResolutionRead(
                id=active.id,
                event_type=active.event_type,
                spool_id=active.spool_id,
                spool_code=active.spool.code if active.spool is not None else None,
                amount_g=active.amount_g,
                sliced_estimated_g=active.sliced_estimated_g,
                remaining_before_g=active.remaining_before_g,
                remaining_after_g=active.remaining_after_g,
                manual_override=active.manual_override,
                reason=active.reason,
                created_at=active.created_at,
            )
        return ReconciliationUsageRead(
            id=usage.id,
            position=usage.position,
            material_type=usage.material_type,
            color=usage.color,
            used_g=usage.used_g,
            progress_estimated_g=_progress_estimated_consumption(job, usage),
            used_m=usage.used_m,
            tray_info_idx=usage.tray_info_idx,
            ams_tray=tray.label if tray is not None else None,
            ams_brand=tray.brand if tray is not None else None,
            candidates=candidates,
            recommended_spool_id=top[0].spool.id if unambiguous else None,
            unambiguous=unambiguous,
            requires_manual_consumption=job.status in _INCOMPLETE_STATUSES,
            resolution=resolution,
        )

    def _rank_candidates(
        self,
        job: PrintJob,
        usage: PrintJobFilamentUsage,
        tray: _TrayEvidence | None,
        spools: list[Spool],
        history: list[PrintJobFilamentReconciliation],
    ) -> list[_RankedCandidate]:
        material = _normalize_material(usage.material_type)
        if not material:
            return []
        color = usage.color or (tray.color if tray is not None else None)
        amount = (
            _progress_estimated_consumption(job, usage)
            or usage.used_g
            or Decimal("0")
        )
        ranked: list[_RankedCandidate] = []
        for spool in spools:
            if _normalize_material(spool.material.name) != material:
                continue
            reasons = [
                ReconciliationCandidateReason(
                    code="MATERIAL_EXACT", detail="Material exactly matches the sliced filament."
                )
            ]
            score = 30
            color_match = _colors_match(color, spool.color_hex, spool.color_name)
            if color_match:
                score += 20
                reasons.append(
                    ReconciliationCandidateReason(
                        code="COLOR_EXACT", detail="Color matches the sliced or AMS color."
                    )
                )
            brand_match = bool(
                tray is not None
                and tray.brand
                and _brand_matches(tray.brand, spool.manufacturer.name, spool.product_name)
            )
            if brand_match:
                score += 15
                reasons.append(
                    ReconciliationCandidateReason(
                        code="BRAND_EXACT", detail="AMS brand matches the inventory manufacturer."
                    )
                )

            historical = _matching_history(job, tray, spool.id, history)
            if historical is not None:
                score += 40
                elapsed = _elapsed_description(job, historical.print_job)
                reasons.append(
                    ReconciliationCandidateReason(
                        code="SAME_AMS_TRAY_HISTORY",
                        detail=f"This spool was confirmed with the same AMS tray fingerprint{elapsed}.",
                    )
                )
            elif spool.last_used_at is not None and _is_recent(spool.last_used_at):
                score += 5
                reasons.append(
                    ReconciliationCandidateReason(
                        code="RECENTLY_USED", detail="This physical spool was used recently."
                    )
                )

            sufficient = spool.current_filament_weight_g >= amount
            if sufficient:
                score += 5
                reasons.append(
                    ReconciliationCandidateReason(
                        code="SUFFICIENT_REMAINING",
                        detail="Remaining inventory covers the sliced estimate.",
                    )
                )
            if spool.status in {SpoolStatus.OPEN, SpoolStatus.IN_USE, SpoolStatus.LOW}:
                score += 3
                reasons.append(
                    ReconciliationCandidateReason(
                        code="ACTIVE_SPOOL", detail="Spool is open and available in inventory."
                    )
                )

            confidence = (
                CandidateConfidence.HIGH
                if historical is not None or (color_match and brand_match)
                else CandidateConfidence.MEDIUM
                if color_match
                else CandidateConfidence.LOW
            )
            ranked.append(_RankedCandidate(spool, score, confidence, reasons, sufficient))
        ranked.sort(key=lambda item: (-item.score, -int(item.sufficient), item.spool.id))
        return ranked

    def _reload_job(self, print_job_id: int) -> ReconciliationJobRead:
        job = self.db.scalar(
            select(PrintJob)
            .where(PrintJob.id == print_job_id)
            .options(
                selectinload(PrintJob.filament_usages)
                .selectinload(PrintJobFilamentUsage.reconciliation_events)
                .selectinload(PrintJobFilamentReconciliation.spool)
            )
        )
        if job is None:
            raise ReconciliationNotFoundError
        return self._build_job(job, self._candidate_spools(), self._active_consumption_history())

    def _validate_eligible(self, job: PrintJob) -> None:
        if (
            job.status not in _TERMINAL_STATUSES
            or job.enrichment_status is not PrintJobEnrichmentStatus.ENRICHED
        ):
            raise ReconciliationConflictError

    def _same_resolution(self, active, item) -> bool:
        if item.action is ReconciliationAction.SKIP:
            return active.event_type is FilamentReconciliationEventType.SKIP
        return (
            active.event_type is FilamentReconciliationEventType.CONSUMPTION
            and active.spool_id == item.spool_id
            and active.amount_g
            == item.consumption_g.quantize(_WEIGHT_QUANTUM)
        )

    def _set_job_status(self, job: PrintJob) -> None:
        job.reconciliation_status = self._derived_job_status(job)

    def _derived_job_status(self, job: PrintJob) -> PrintJobReconciliationStatus:
        active = [usage.current_reconciliation for usage in job.filament_usages]
        resolved = [event for event in active if event is not None]
        if resolved and len(resolved) == len(active):
            if all(event.event_type is FilamentReconciliationEventType.SKIP for event in resolved):
                return PrintJobReconciliationStatus.NOT_APPLICABLE
            return PrintJobReconciliationStatus.RECONCILED
        if resolved:
            return PrintJobReconciliationStatus.PARTIALLY_RECONCILED
        if job.status in _INCOMPLETE_STATUSES:
            return PrintJobReconciliationStatus.NEEDS_REVIEW
        return PrintJobReconciliationStatus.PENDING

    def _begin_immediate(self) -> None:
        bind = self.db.get_bind()
        if bind.dialect.name == "sqlite" and not self.db.in_transaction():
            try:
                self.db.execute(text("BEGIN IMMEDIATE"))
            except SQLAlchemyError as error:
                self.db.rollback()
                raise ReconciliationConflictError from error


def _normalize(value: object | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())


def _progress_estimated_consumption(
    job: PrintJob,
    usage: PrintJobFilamentUsage,
) -> Decimal | None:
    """Return the sliced usage adjusted by captured progress for incomplete jobs."""
    if usage.used_g is None:
        return None
    sliced = Decimal(usage.used_g)
    if job.status not in _INCOMPLETE_STATUSES:
        return sliced.quantize(_WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)
    if job.final_progress is None:
        return None
    return (
        sliced * Decimal(job.final_progress) / Decimal("100")
    ).quantize(_WEIGHT_QUANTUM, rounding=ROUND_HALF_UP)


def _latest_checkpoint(spool: Spool) -> datetime | None:
    active = [
        event.effective_at
        for event in spool.calibrations
        if event.event_type is CalibrationEventType.PHYSICAL_CALIBRATION
        and event.reversed_at is None
    ]
    return max(active) if active else None


def _comparable_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _normalize_material(value: str | None) -> str:
    return _normalize(value)


def _hex_color(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lstrip("#").upper()
    if len(normalized) == 8:
        normalized = normalized[:6]
    return normalized if re.fullmatch(r"[0-9A-F]{6}", normalized) else None


def _colors_match(source: str | None, color_hex: str | None, color_name: str) -> bool:
    source_hex = _hex_color(source)
    inventory_hex = _hex_color(color_hex)
    if source_hex and inventory_hex:
        return source_hex == inventory_hex
    return bool(source and _normalize(source) == _normalize(color_name))


def _brand_matches(brand: str, manufacturer: str, product_name: str | None) -> bool:
    normalized_brand = _normalize(brand)
    return normalized_brand in {_normalize(manufacturer), _normalize(product_name)} or (
        normalized_brand and normalized_brand in _normalize(product_name)
    )


def _tray_evidence(
    snapshot: dict[str, object] | None,
    usage: PrintJobFilamentUsage,
) -> _TrayEvidence | None:
    if not isinstance(snapshot, dict):
        return None
    trays: list[_TrayEvidence] = []
    units = snapshot.get("ams_units")
    if isinstance(units, list):
        for unit in units:
            if not isinstance(unit, dict):
                continue
            unit_id = str(unit.get("unit_id") or "?")
            unit_trays = unit.get("trays")
            if not isinstance(unit_trays, list):
                continue
            for tray in unit_trays:
                if isinstance(tray, dict):
                    trays.append(_tray_from_dict(f"AMS {unit_id}:{tray.get('tray_id', '?')}", tray))
    external = snapshot.get("external_tray")
    if isinstance(external, dict):
        trays.append(_tray_from_dict(f"External:{external.get('tray_id', '?')}", external))
    if not trays:
        return None

    profile_matches = [
        tray
        for tray in trays
        if usage.tray_info_idx
        and usage.tray_info_idx in {tray.profile_id, tray.setting_id}
    ]
    if len(profile_matches) == 1:
        return profile_matches[0]

    current = str(snapshot.get("current_tray") or "")
    current_matches = [tray for tray in trays if tray.label.endswith(f":{current}")]
    compatible = [
        tray
        for tray in trays
        if _normalize_material(tray.material) == _normalize_material(usage.material_type)
        and (not usage.color or _colors_match(usage.color, tray.color, tray.color or ""))
    ]
    if len(compatible) == 1:
        return compatible[0]
    for tray in current_matches:
        if tray in compatible:
            return tray
    return current_matches[0] if len(current_matches) == 1 else None


def _tray_from_dict(label: str, tray: dict[str, object]) -> _TrayEvidence:
    def value(key: str) -> str | None:
        item = tray.get(key)
        return str(item) if item not in {None, ""} else None

    return _TrayEvidence(
        label=label,
        material=value("material_type"),
        color=value("color"),
        brand=value("brand"),
        profile_id=value("profile_id"),
        setting_id=value("setting_id"),
        tag_uid=value("tag_uid"),
        tray_uuid=value("tray_uuid"),
    )


def _matching_history(
    job: PrintJob,
    tray: _TrayEvidence | None,
    spool_id: int,
    history: list[PrintJobFilamentReconciliation],
) -> PrintJobFilamentReconciliation | None:
    if tray is None:
        return None
    job_time = job.finished_at or job.created_at
    for event in history:
        if event.spool_id != spool_id or event.print_job_id == job.id:
            continue
        historical_time = event.print_job.finished_at or event.print_job.created_at
        elapsed = _aware(job_time) - _aware(historical_time)
        if elapsed < timedelta(0) or elapsed > timedelta(days=7):
            continue
        historical_tray = _tray_evidence(
            event.print_job.ams_snapshot, event.filament_usage
        )
        if historical_tray is not None and historical_tray.fingerprint == tray.fingerprint:
            return event
    return None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _elapsed_description(current: PrintJob, previous: PrintJob) -> str:
    current_at = _aware(current.finished_at or current.created_at)
    previous_at = _aware(previous.finished_at or previous.created_at)
    hours = max(0, int((current_at - previous_at).total_seconds() // 3600))
    return f" about {hours}h earlier" if hours < 48 else " on an earlier print"


def _is_recent(value: datetime) -> bool:
    return _aware(value) >= _aware(utc_now()) - timedelta(days=14)

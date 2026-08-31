from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Location,
    Manufacturer,
    Material,
    Spool,
    SpoolStatus,
    WeightHistory,
)
from app.services.spool_weight_service import (
    SpoolWeightOutOfRangeError,
    apply_spool_weight_update,
)
from app.models.timestamps import utc_now
from app.schemas import (
    SpoolCreate,
    SpoolFilterParams,
    SpoolUpdate,
    WeightHistoryCreate,
)
from app.services.spool_code_service import add_spool_with_generated_code
from app.services.spool_status_service import update_inventory_status


class SpoolNotFoundError(Exception):
    """Raised when a requested spool does not exist."""


class SpoolManufacturerNotFoundError(Exception):
    """Raised when a referenced manufacturer does not exist."""


class SpoolMaterialNotFoundError(Exception):
    """Raised when a referenced material does not exist."""


class SpoolLocationNotFoundError(Exception):
    """Raised when a referenced location does not exist."""


class SpoolMustBeArchivedError(Exception):
    """Raised when physical deletion is requested for an active spool."""


class SpoolDataConflictError(Exception):
    """Raised when a database constraint prevents a spool operation."""


class SpoolArchivedUpdateError(Exception):
    """Raised when a mutable operation targets an archived spool."""


class SpoolInUseArchiveError(Exception):
    """Raised when an active print still owns the spool."""


class SpoolWeightExceedsInitialError(Exception):
    """Raised when a measurement exceeds the spool's initial weight."""


class SpoolService:
    """Apply spool rules and coordinate database transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_spools(
        self,
        filters: SpoolFilterParams | None = None,
    ) -> list[Spool]:
        filters = filters or SpoolFilterParams()
        conditions = []

        if (
            not filters.include_archived
            and filters.status is not SpoolStatus.ARCHIVED
        ):
            conditions.extend(
                [
                    Spool.status != SpoolStatus.ARCHIVED,
                    Spool.archived_at.is_(None),
                ]
            )

        if filters.manufacturer_id is not None:
            conditions.append(Spool.manufacturer_id == filters.manufacturer_id)
        if filters.material_id is not None:
            conditions.append(Spool.material_id == filters.material_id)
        if filters.location_id is not None:
            conditions.append(Spool.location_id == filters.location_id)
        if filters.status is not None:
            conditions.append(Spool.status == filters.status)
        if filters.needs_drying is not None:
            conditions.append(Spool.needs_drying == filters.needs_drying)
        if filters.min_weight_g is not None:
            conditions.append(
                Spool.current_filament_weight_g >= filters.min_weight_g
            )
        if filters.max_weight_g is not None:
            conditions.append(
                Spool.current_filament_weight_g <= filters.max_weight_g
            )
        if filters.min_remaining_percent is not None:
            conditions.append(
                Spool.current_filament_weight_g * 100
                >= filters.min_remaining_percent
                * Spool.initial_filament_weight_g
            )
        if filters.max_remaining_percent is not None:
            conditions.append(
                Spool.current_filament_weight_g * 100
                <= filters.max_remaining_percent
                * Spool.initial_filament_weight_g
            )
        if filters.search is not None:
            search_pattern = self._like_contains_pattern(filters.search)
            conditions.append(
                or_(
                    Spool.code.ilike(search_pattern, escape="\\"),
                    Spool.display_name.ilike(search_pattern, escape="\\"),
                    Spool.product_name.ilike(search_pattern, escape="\\"),
                    Spool.color_name.ilike(search_pattern, escape="\\"),
                    Spool.manufacturer.has(
                        Manufacturer.name.ilike(search_pattern, escape="\\")
                    ),
                    Spool.material.has(
                        Material.name.ilike(search_pattern, escape="\\")
                    ),
                    Spool.location.has(
                        Location.name.ilike(search_pattern, escape="\\")
                    ),
                )
            )

        statement = (
            self._spool_query()
            .where(*conditions)
            .order_by(Spool.code.asc(), Spool.id.asc())
        )
        return list(self.db.scalars(statement).all())

    def get_spool_by_code(self, code: str) -> Spool:
        spool = self.db.scalar(
            self._spool_query().where(Spool.code == self._normalize_code(code))
        )
        if spool is None:
            raise SpoolNotFoundError
        return spool

    def create_spool(self, payload: SpoolCreate) -> Spool:
        self._validate_all_references(
            payload.manufacturer_id,
            payload.material_id,
            payload.location_id,
        )
        spool = Spool(**payload.model_dump())
        update_inventory_status(spool)
        if spool.status is SpoolStatus.ARCHIVED:
            spool.archived_at = utc_now()

        try:
            add_spool_with_generated_code(self.db, spool)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise SpoolDataConflictError from error

        return self.get_spool_by_code(spool.code)

    def update_spool(self, code: str, payload: SpoolUpdate) -> Spool:
        spool = self.get_spool_by_code(code)
        changes = payload.model_dump(exclude_unset=True)
        self._validate_changed_references(changes)

        current_state = {
            field: getattr(spool, field) for field in SpoolCreate.model_fields
        }
        validated_state = SpoolCreate.model_validate(current_state | changes)

        for field in changes:
            setattr(spool, field, getattr(validated_state, field))

        update_inventory_status(spool)
        if (
            spool.status is SpoolStatus.ARCHIVED
            and spool.archived_at is None
        ):
            spool.archived_at = utc_now()

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise SpoolDataConflictError from error

        return self.get_spool_by_code(spool.code)

    def update_weight(
        self,
        code: str,
        payload: WeightHistoryCreate,
    ) -> Spool:
        spool = self.get_spool_by_code(code)
        if self._is_archived(spool):
            raise SpoolArchivedUpdateError
        try:
            apply_spool_weight_update(
                self.db,
                spool,
                payload.weight_g,
                payload.source,
                payload.notes,
            )
            self.db.commit()
        except SpoolWeightOutOfRangeError as error:
            self.db.rollback()
            raise SpoolWeightExceedsInitialError from error
        except SQLAlchemyError as error:
            self.db.rollback()
            raise SpoolDataConflictError from error

        return self.get_spool_by_code(spool.code)

    def archive_spool(self, code: str) -> Spool:
        spool = self.get_spool_by_code(code)
        if (
            spool.status is SpoolStatus.ARCHIVED
            and spool.archived_at is not None
        ):
            return spool

        if spool.status is SpoolStatus.IN_USE:
            raise SpoolInUseArchiveError

        spool.status = SpoolStatus.ARCHIVED
        if spool.archived_at is None:
            spool.archived_at = utc_now()

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise SpoolDataConflictError from error

        return self.get_spool_by_code(spool.code)

    def delete_spool(self, code: str) -> None:
        spool = self.get_spool_by_code(code)
        if not self._is_archived(spool):
            raise SpoolMustBeArchivedError

        self.db.delete(spool)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise SpoolDataConflictError from error

    @staticmethod
    def _normalize_code(code: str) -> str:
        return code.strip().upper()

    @staticmethod
    def _like_contains_pattern(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%")
        escaped = escaped.replace("_", "\\_")
        return f"%{escaped}%"

    @staticmethod
    def _is_archived(spool: Spool) -> bool:
        return (
            spool.status is SpoolStatus.ARCHIVED
            or spool.archived_at is not None
        )

    @staticmethod
    def _spool_query():
        return select(Spool).options(
            joinedload(Spool.manufacturer),
            joinedload(Spool.material),
            joinedload(Spool.location),
        ).execution_options(populate_existing=True)

    def _validate_all_references(
        self,
        manufacturer_id: int,
        material_id: int,
        location_id: int | None,
    ) -> None:
        self._validate_manufacturer(manufacturer_id)
        self._validate_material(material_id)
        if location_id is not None:
            self._validate_location(location_id)

    def _validate_changed_references(self, changes: dict[str, object]) -> None:
        if "manufacturer_id" in changes:
            self._validate_manufacturer(changes["manufacturer_id"])
        if "material_id" in changes:
            self._validate_material(changes["material_id"])
        if "location_id" in changes and changes["location_id"] is not None:
            self._validate_location(changes["location_id"])

    def _validate_manufacturer(self, manufacturer_id: object) -> None:
        if self.db.get(Manufacturer, manufacturer_id) is None:
            raise SpoolManufacturerNotFoundError

    def _validate_material(self, material_id: object) -> None:
        if self.db.get(Material, material_id) is None:
            raise SpoolMaterialNotFoundError

    def _validate_location(self, location_id: object) -> None:
        if self.db.get(Location, location_id) is None:
            raise SpoolLocationNotFoundError

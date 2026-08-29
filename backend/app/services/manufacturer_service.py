from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Manufacturer, Spool
from app.schemas import ManufacturerCreate, ManufacturerUpdate


class ManufacturerNotFoundError(Exception):
    """Raised when a requested manufacturer does not exist."""


class ManufacturerNameConflictError(Exception):
    """Raised when a manufacturer name is already in use."""


class ManufacturerInUseError(Exception):
    """Raised when a manufacturer is referenced by a spool."""


class ManufacturerService:
    """Apply manufacturer rules and coordinate database transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_manufacturers(self) -> list[Manufacturer]:
        statement = select(Manufacturer).order_by(
            func.lower(Manufacturer.name).asc(),
            Manufacturer.name.asc(),
            Manufacturer.id.asc(),
        )
        return list(self.db.scalars(statement).all())

    def get_manufacturer(self, manufacturer_id: int) -> Manufacturer:
        manufacturer = self.db.get(Manufacturer, manufacturer_id)
        if manufacturer is None:
            raise ManufacturerNotFoundError
        return manufacturer

    def create_manufacturer(self, payload: ManufacturerCreate) -> Manufacturer:
        manufacturer = Manufacturer(**payload.model_dump(mode="json"))
        self.db.add(manufacturer)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ManufacturerNameConflictError from error

        self.db.refresh(manufacturer)
        return manufacturer

    def update_manufacturer(
        self,
        manufacturer_id: int,
        payload: ManufacturerUpdate,
    ) -> Manufacturer:
        manufacturer = self.get_manufacturer(manufacturer_id)
        changes = payload.model_dump(mode="json", exclude_unset=True)

        for field, value in changes.items():
            setattr(manufacturer, field, value)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ManufacturerNameConflictError from error

        self.db.refresh(manufacturer)
        return manufacturer

    def delete_manufacturer(self, manufacturer_id: int) -> None:
        manufacturer = self.get_manufacturer(manufacturer_id)
        spool_reference = self.db.scalar(
            select(Spool.id)
            .where(Spool.manufacturer_id == manufacturer_id)
            .limit(1)
        )
        if spool_reference is not None:
            raise ManufacturerInUseError

        self.db.delete(manufacturer)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ManufacturerInUseError from error

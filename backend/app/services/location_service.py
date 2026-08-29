from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Location, Spool
from app.schemas import LocationCreate, LocationUpdate


class LocationNotFoundError(Exception):
    """Raised when a requested location does not exist."""


class LocationNameConflictError(Exception):
    """Raised when a location name is already in use."""


class LocationInUseError(Exception):
    """Raised when a location is referenced by a spool."""


class LocationService:
    """Apply location rules and coordinate database transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_locations(self) -> list[Location]:
        statement = select(Location).order_by(
            func.lower(Location.name).asc(),
            Location.name.asc(),
            Location.id.asc(),
        )
        return list(self.db.scalars(statement).all())

    def get_location(self, location_id: int) -> Location:
        location = self.db.get(Location, location_id)
        if location is None:
            raise LocationNotFoundError
        return location

    def create_location(self, payload: LocationCreate) -> Location:
        location = Location(**payload.model_dump())
        self.db.add(location)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise LocationNameConflictError from error

        self.db.refresh(location)
        return location

    def update_location(
        self,
        location_id: int,
        payload: LocationUpdate,
    ) -> Location:
        location = self.get_location(location_id)
        changes = payload.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(location, field, value)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise LocationNameConflictError from error

        self.db.refresh(location)
        return location

    def delete_location(self, location_id: int) -> None:
        location = self.get_location(location_id)
        spool_reference = self.db.scalar(
            select(Spool.id).where(Spool.location_id == location_id).limit(1)
        )
        if spool_reference is not None:
            raise LocationInUseError

        self.db.delete(location)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise LocationInUseError from error

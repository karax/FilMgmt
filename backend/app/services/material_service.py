from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Material, Spool
from app.schemas import MaterialCreate, MaterialUpdate


class MaterialNotFoundError(Exception):
    """Raised when a requested material does not exist."""


class MaterialNameConflictError(Exception):
    """Raised when a material name is already in use."""


class MaterialInUseError(Exception):
    """Raised when a material is referenced by a spool."""


class MaterialService:
    """Apply material rules and coordinate database transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_materials(self) -> list[Material]:
        statement = select(Material).order_by(
            func.lower(Material.name).asc(),
            Material.name.asc(),
            Material.id.asc(),
        )
        return list(self.db.scalars(statement).all())

    def get_material(self, material_id: int) -> Material:
        material = self.db.get(Material, material_id)
        if material is None:
            raise MaterialNotFoundError
        return material

    def create_material(self, payload: MaterialCreate) -> Material:
        material = Material(**payload.model_dump())
        self.db.add(material)

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise MaterialNameConflictError from error

        self.db.refresh(material)
        return material

    def update_material(
        self,
        material_id: int,
        payload: MaterialUpdate,
    ) -> Material:
        material = self.get_material(material_id)
        changes = payload.model_dump(exclude_unset=True)
        current_state = {
            field: getattr(material, field)
            for field in MaterialCreate.model_fields
        }
        validated_state = MaterialCreate.model_validate(current_state | changes)

        for field in changes:
            setattr(material, field, getattr(validated_state, field))

        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise MaterialNameConflictError from error

        self.db.refresh(material)
        return material

    def delete_material(self, material_id: int) -> None:
        material = self.get_material(material_id)
        spool_reference = self.db.scalar(
            select(Spool.id).where(Spool.material_id == material_id).limit(1)
        )
        if spool_reference is not None:
            raise MaterialInUseError

        self.db.delete(material)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise MaterialInUseError from error

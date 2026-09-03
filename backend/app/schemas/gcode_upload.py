from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UtcDatetime


class GCodeUploadRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    filename: str
    size_bytes: int
    created_at: UtcDatetime
    status: Literal["UPLOADED"] = "UPLOADED"

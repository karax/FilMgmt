from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.spool import Spool


def format_spool_code(spool_id: int) -> str:
    """Format a database-generated spool ID as a stable human code."""
    if (
        not isinstance(spool_id, int)
        or isinstance(spool_id, bool)
        or spool_id <= 0
    ):
        raise ValueError("spool ID must be a positive integer")

    return f"FIL-{spool_id:04d}"


def add_spool_with_generated_code(session: Session, spool: Spool) -> Spool:
    """Add a new spool and assign its final code without counting rows.

    The temporary unique value satisfies the non-null/unique database rules
    while the first flush obtains the database-generated ID. The final code is
    then updated in the same transaction. The caller retains commit control.
    """
    if spool.id is not None:
        raise ValueError("spool must be transient before code generation")

    spool.code = f"PENDING-{uuid4().hex}"
    session.add(spool)
    session.flush()

    spool.code = format_spool_code(spool.id)
    session.flush()
    return spool

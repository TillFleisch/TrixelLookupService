"""Database wrappers related to Trixel Management Servers."""

from secrets import token_bytes

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import except_columns

from . import model

MAX_INTEGRITY_ERROR_RETRIES = 10


def create_tms(db: Session, host: str) -> model.TrixelManagementServer:
    """
    Generate an authentication token and create a new TMS entry within the database.

    :param host: host address
    :returns: Inserted TMS with auth token
    :raises RuntimeError: If insertion failed (due to invalid token generation)
    """
    retries = 0
    while True:
        try:
            tms = model.TrixelManagementServer(host=host, token=token_bytes(32))
            db.add(tms)
            db.commit()
            db.refresh(tms)
            return tms
        except IntegrityError as e:
            db.rollback()
            retries += 1
            if retries >= MAX_INTEGRITY_ERROR_RETRIES:
                raise e
            continue


def get_tms_list(
    db: Session,
    active: bool = None,
    limit: int = 100,
    offset: int = 0,
) -> list[int]:
    """
    Get a list of all registered TMSs.

    :param active: filters by active/inactive or both
    :param limit: search result limit
    :param offset: skips the first n results
    :returns: list of TMS IDs
    """
    query = db.query(model.TrixelManagementServer.id)
    if active is not None:
        query = query.where(model.TrixelManagementServer.active == active)
    result = query.offset(offset=offset).limit(limit=limit).all()
    return [x[0] for x in result]


def get_tms(
    db: Session,
    tms_id: int = None,
    active: bool = None,
    limit: int = 100,
    offset: int = 0,
) -> list[model.TrixelManagementServer]:
    """
    Get TMS details from the database.

    :param tms_id: limit results to the provided id
    :param active: filters by active/inactive or both
    :param limit: search result limit
    :param offset: skips the first n results
    :returns: List of detailed TMS entries
    """
    query = db.query(*except_columns(model.TrixelManagementServer, "token"))
    if tms_id is not None:
        query = query.where(model.TrixelManagementServer.id == tms_id)
    if active is not None:
        query = query.where(model.TrixelManagementServer.active == active)
    return query.offset(offset=offset).limit(limit=limit).all()


def verify_tms_token(db: Session, token: bytes):
    """
    Check authentication token validity.

    :param token: user provided token
    :return: TMS id associated with the token
    :raises PermissionError: if the provided token does not exist
    """
    if (
        trixel_id := db.query(model.TrixelManagementServer.id)
        .where(model.TrixelManagementServer.token == token)
        .first()
    ):
        return trixel_id[0]
    raise PermissionError("Invalid TMS authentication token.")


def update_tms(
    db: Session, id: int, active: bool | None = None, host: str | None = None
) -> model.TrixelManagementServer:
    """Update TMS properties within the database.

    :param id: id of the TMS in question
    :param active: new active status of the TMS
    :param host: new address of the TMS
    :returns: updates TMS entry
    :raises ValueError: if neither active not host are given
    """
    stmt = update(model.TrixelManagementServer).where(model.TrixelManagementServer.id == id)

    if active is None and host is None:
        raise ValueError("At least one of [host, active] must be provided.")

    if active is not None:
        stmt = stmt.values(active=active)
    if host is not None:
        stmt = stmt.values(host=host)

    result = db.execute(stmt)
    if result.rowcount == 0:
        db.rollback()
        raise ValueError("No TMS with the provided id exists!")

    db.commit()

    return db.query(*except_columns(model.TrixelManagementServer)).where(model.TrixelManagementServer.id == id).first()

"""Database wrappers related to Trixel Management Servers."""

from secrets import token_bytes

from pydantic import PositiveInt
from pynyhtm import HTM
from sqlalchemy import and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from crud import add_level_lookup
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

        # Remove all TMS delegations
        if not active:
            db.query().filter(model.TrixelManagementServer.id == id).delete()

    if host is not None:
        stmt = stmt.values(host=host)

    result = db.execute(stmt)
    if result.rowcount == 0:
        db.rollback()
        raise ValueError("No TMS with the provided id exists!")

    db.commit()

    return db.query(*except_columns(model.TrixelManagementServer)).where(model.TrixelManagementServer.id == id).first()


def insert_delegations(db: Session, tms_id: int, trixel_ids: list[int]) -> model.TMSDelegation:
    """
    Insert one or more trixel delegations into the database.

    note:: This currently only implements insertions without conflict handling and trixel exclusion.

    :param tms_id: id of the TMS in charge
    :param trixel_ids: list of ids which are delegated
    :returns: list of TMS delegations
    :raises ValueError: if one of trixel ids is invalid
    """
    tms: model.TrixelManagementServer = (
        db.query(*except_columns(model.TrixelManagementServer)).where(model.TrixelManagementServer.id == tms_id).first()
    )
    if not tms.active:
        raise RuntimeError("Trixels cannot be delegated to deactivated TMS.")

    delegations = list()
    level_lookup = dict()
    for trixel in trixel_ids:
        try:
            level = HTM.get_level(trixel)
        except ValueError:
            raise ValueError(f"Invalid trixel id: {trixel}")
        tms_delegation = model.TMSDelegation(tms_id=tms.id, trixel_id=trixel)
        db.add(tms_delegation)
        delegations.append(tms_delegation)
        level_lookup[trixel] = level

    add_level_lookup(db, level_lookup)
    db.commit()

    for tms_delegation in delegations:
        db.refresh(tms_delegation)
    return delegations


def get_all_delegations(
    db: Session,
    limit: PositiveInt = 100,
    offset: int = 0,
) -> list[model.TMSDelegation]:
    """
    Get a list of all delegations.

    :param limit: search result limit
    :param offset: skips the first n results
    :returns: list of TMSDelegations
    """
    return (
        db.query(model.TMSDelegation)
        .join(
            model.TrixelManagementServer,
            and_(
                model.TMSDelegation.tms_id == model.TrixelManagementServer.id,
                model.TrixelManagementServer.active == True,  # noqa: E712
            ),
        )
        .offset(offset=offset)
        .limit(limit=limit)
        .all()
    )


def get_tms_delegations(db: Session, tms_id: int) -> list[model.TMSDelegation]:
    """
    Get all delegations for a TMS including delegations from excluded trixels.

    :param tms_id: id of the TMS for which delegations are determined
    :returns: list of TMSDelegations
    :raises ValueError: if the a tms with ID does not exists
    """
    if db.query(model.TrixelManagementServer.id).where(model.TrixelManagementServer.id == tms_id).first() is None:
        raise ValueError(f"TMS with ID {tms_id} does not exist.")

    self = aliased(model.TMSDelegation)

    res = (
        db.query(model.TMSDelegation, self)
        .where(model.TMSDelegation.tms_id == tms_id)
        .join(
            model.TrixelManagementServer,
            and_(
                model.TMSDelegation.tms_id == model.TrixelManagementServer.id,
                model.TrixelManagementServer.active == True,  # noqa: E712
            ),
        )
        .join(
            self,
            and_(
                model.TMSDelegation.trixel_id == self.trixel_id,
                model.TMSDelegation.exclude == True,  # noqa: E712
                self.exclude == False,  # noqa: E712
            ),
            isouter=True,
        )
        .all()
    )

    flat = list()
    for r in res:
        flat.append(r[0])
        if r[1] is not None:
            flat.append(r[1])
    return flat

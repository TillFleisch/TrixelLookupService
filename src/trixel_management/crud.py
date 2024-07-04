"""Database wrappers related to Trixel Management Servers."""

from secrets import token_bytes

import jwt
from pydantic import PositiveInt
from pynyhtm import HTM
from sqlalchemy import and_, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from crud import add_level_lookup
from database import except_columns

from . import model

MAX_INTEGRITY_ERROR_RETRIES = 10


async def create_tms(db: AsyncSession, host: str) -> model.TrixelManagementServer:
    """
    Generate an authentication token and create a new TMS entry within the database.

    :param host: host address
    :returns: Inserted TMS with auth token
    :raises RuntimeError: If insertion failed (due to invalid token generation)
    """
    retries = 0
    while True:
        try:
            tms = model.TrixelManagementServer(host=host, token_secret=token_bytes(256))
            db.add(tms)
            await db.commit()
            await db.refresh(tms)
            return tms
        except IntegrityError as e:
            await db.rollback()
            retries += 1
            if retries >= MAX_INTEGRITY_ERROR_RETRIES:
                raise e
            continue


async def get_tms_list(
    db: AsyncSession,
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
    query = select(model.TrixelManagementServer.id)
    if active is not None:
        query = query.where(model.TrixelManagementServer.active == active)
    query = query.offset(offset=offset).limit(limit=limit)

    return (await db.execute(query)).scalars().all()


async def get_tms(
    db: AsyncSession,
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
    query = select(*except_columns(model.TrixelManagementServer, "token_secret"))
    if tms_id is not None:
        query = query.where(model.TrixelManagementServer.id == tms_id)
    if active is not None:
        query = query.where(model.TrixelManagementServer.active == active)
    query = query.offset(offset=offset).limit(limit=limit)
    return (await db.execute(query)).all()


async def verify_tms_token(db: AsyncSession, jwt_token: bytes):
    """
    Check authentication token validity.

    :param jwt_token: user provided token
    :return: TMS id associated with the token
    :raises PermissionError: if the provided token does not exist
    """
    try:
        unverified_payload = jwt.decode(jwt_token, options={"verify_signature": False}, algorithms=["HS256"])
        query = select(model.TrixelManagementServer.token_secret).where(
            model.TrixelManagementServer.id == unverified_payload["tms_id"]
        )
        if token_secret := (await db.execute(query)).scalars().first():
            payload = jwt.decode(jwt_token, token_secret, algorithms=["HS256"])
            return payload["tms_id"]
    except jwt.PyJWTError:
        raise PermissionError("Invalid TMS authentication token.")
    raise PermissionError("Invalid TMS authentication token.")


async def update_tms(
    db: AsyncSession, id: int, active: bool | None = None, host: str | None = None
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
            await db.execute(delete(model.TrixelManagementServer).filter(model.TrixelManagementServer.id == id))

    if host is not None:
        stmt = stmt.values(host=host)

    result = await db.execute(stmt)
    if result.rowcount == 0:
        await db.rollback()
        raise ValueError("No TMS with the provided id exists!")

    await db.commit()

    # Update with returning not supported by mysql
    query = select(*except_columns(model.TrixelManagementServer, "token_secret")).where(
        model.TrixelManagementServer.id == id
    )
    return (await db.execute(query)).one()


async def insert_delegations(db: AsyncSession, tms_id: int, trixel_ids: list[int]) -> model.TMSDelegation:
    """
    Insert one or more trixel delegations into the database.

    note:: This currently only implements insertions without conflict handling and trixel exclusion.

    :param tms_id: id of the TMS in charge
    :param trixel_ids: list of ids which are delegated
    :returns: list of TMS delegations
    :raises ValueError: if one of trixel ids is invalid
    """
    query = select(*except_columns(model.TrixelManagementServer, "token_secret")).where(
        model.TrixelManagementServer.id == tms_id
    )
    tms: model.TrixelManagementServer = (await db.execute(query)).first()

    if tms is None:
        raise RuntimeError(f"TMS with id {tms_id} does not exist!")

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

    await add_level_lookup(db, level_lookup)
    await db.commit()

    for tms_delegation in delegations:
        await db.refresh(tms_delegation)
    return delegations


async def get_all_delegations(
    db: AsyncSession,
    limit: PositiveInt = 100,
    offset: int = 0,
) -> list[model.TMSDelegation]:
    """
    Get a list of all delegations.

    :param limit: search result limit
    :param offset: skips the first n results
    :returns: list of TMSDelegations
    """
    query = (
        select(model.TMSDelegation)
        .join(
            model.TrixelManagementServer,
            and_(
                model.TMSDelegation.tms_id == model.TrixelManagementServer.id,
                model.TrixelManagementServer.active == True,  # noqa: E712
            ),
        )
        .offset(offset=offset)
        .limit(limit=limit)
    )
    return (await db.execute(query)).scalars().all()


async def get_tms_delegations(db: AsyncSession, tms_id: int) -> list[model.TMSDelegation]:
    """
    Get all delegations for a TMS including delegations from excluded trixels.

    :param tms_id: id of the TMS for which delegations are determined
    :returns: list of TMSDelegations
    :raises ValueError: if the a tms with ID does not exists
    """
    query = select(model.TrixelManagementServer.id).where(model.TrixelManagementServer.id == tms_id)
    if (await db.execute(query)).scalars().first() is None:
        raise ValueError(f"TMS with ID {tms_id} does not exist.")

    self = aliased(model.TMSDelegation)

    res = (
        select(model.TMSDelegation, self)
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
    )
    res = (await db.execute(res)).all()

    flat = list()
    for r in res:
        flat.append(r[0])
        if r[1] is not None:
            flat.append(r[1])
    return flat

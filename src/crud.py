"""Global database wrappers."""

from pydantic import NonNegativeInt, PositiveInt
from pynyhtm import HTM
from sqlalchemy import and_, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import model
from trixel_management.model import TMSDelegation, TrixelManagementServer


async def init_measurement_type_enum(db: AsyncSession):
    """Initialize the measurement type reference enum table within the DB."""
    query = select(model.MeasurementType)
    existing_types: model.MeasurementType = (await db.execute(query)).scalars().all()
    existing_types: set[int, str] = set([(x.id, x.name) for x in existing_types])

    enum_types: set[int, str] = set()
    for type_ in model.MeasurementTypeEnum:
        enum_types.add((type_.get_id(), type_.value))

    # Assert the local python enum is the same as the one used in the DB
    # Thus, the local enum can be used as a shortcut without retrieving from the enum relation
    if len(existing_types - enum_types) > 0:
        raise (RuntimeError("DB contains unsupported enums!"))

    new_types = enum_types - existing_types
    if len(new_types) > 0:
        for new_type in new_types:
            db.add(model.MeasurementType(id=new_type[0], name=new_type[1]))
        await db.commit()


async def add_level_lookup(db: AsyncSession, lookup: dict[int, int]):
    """Insert an entry within the level lookup table.

    Adds all non-existent entries. Does not commit changes.

    :param lookup: dict containing the level for each trixel
    :param level: level at which the trixel is located
    """
    clauses = list()
    for trixel_id in lookup.keys():
        clauses.append(model.LevelLookup.trixel_id == trixel_id)

    query = select(model.LevelLookup.trixel_id).where(or_(*clauses))
    existing_trixels = (await db.execute(query)).scalars().all()

    new_trixels = lookup.keys() - set(existing_trixels)
    for trixel_id in new_trixels:
        db.add(model.LevelLookup(trixel_id=trixel_id, level=lookup[trixel_id]))


async def create_trixel_map(
    db: AsyncSession, trixel_id: int, type_: model.MeasurementTypeEnum, sensor_count: int
) -> model.TrixelMap:
    """
    Create an entry in the trixel map for a given trixel id and measurement type.

    :param trixel_id: ID of the trixel in question
    :param type_: measurement type
    :param sensor_count: initial sensor_count value
    :returns: The added trixel
    :raises ValueError: if the trixel id is invalid
    """
    try:
        level = HTM.get_level(trixel_id)

        query = select(model.MeasurementType.id).where(model.MeasurementType.name == type_.value)
        type_id: model.MeasurementType = (await db.execute(query)).scalars().one()

        trixel = model.TrixelMap(id=trixel_id, type_id=type_id, sensor_count=sensor_count)
        db.add(trixel)
        await add_level_lookup(db, {trixel_id: level})
        await db.commit()

        return trixel

    except ValueError:
        raise ValueError(f"Invalid trixel id: {trixel_id}")


async def update_trixel_map(
    db: AsyncSession, trixel_id: int, type_: model.MeasurementTypeEnum, sensor_count: int
) -> model.TrixelMap | None:
    """
    Update an entry within the trixel map for a given trixel id and measurement type.

    :param trixel_id: id of the trixel in question
    :param type_: measurement type
    :param sensor_count: the new value
    :return: updated TrixelMap or None if no row was affected
    """
    stmt = (
        update(model.TrixelMap)
        .where(
            model.TrixelMap.id == trixel_id,
            model.TrixelMap.type_id == model.MeasurementType.id,
            model.MeasurementType.name == type_.value,
        )
        .values(sensor_count=sensor_count)
    )

    result = await db.execute(stmt)
    if result.rowcount == 0:
        await db.rollback()
        return None

    await db.commit()

    # Update with returning not supported by mysql
    query = select(model.TrixelMap).where(
        model.TrixelMap.id == trixel_id,
        model.TrixelMap.type_id == model.MeasurementType.id,
        model.MeasurementType.name == type_.value,
    )
    return (await db.execute(query)).scalars().one()


async def upsert_trixel_map(
    db: AsyncSession, trixel_id: int, type_: model.MeasurementTypeEnum, sensor_count: int
) -> model.TrixelMap:
    """
    Update or insert into the trixel map if not present.

    :param trixel_id: id of the trixel in question
    :param type_: measurement type
    :param sensor_count: new value
    :return: updated/inserted trixel
    """
    if trixel := await update_trixel_map(db, trixel_id, type_, sensor_count):
        return trixel
    else:
        return await create_trixel_map(db, trixel_id, type_, sensor_count)


async def batch_upsert_trixel_map(
    db: AsyncSession, type_: model.MeasurementTypeEnum, updates: dict[int, NonNegativeInt]
) -> None:
    """
    Update or insert multiple entries into the trixel map if not present.

    :param update: map which holds the sensor count for different trixel IDs
    :param type_: measurement type for which the sensor map is updated
    :raises ValueError: if the trixel id is invalid
    """
    # TODO: use bulk insert/update
    for trixel_id, sensor_count in updates.items():
        await upsert_trixel_map(db, trixel_id=trixel_id, sensor_count=sensor_count, type_=type_)


async def get_trixel_map(
    db: AsyncSession, trixel_id: int, types: list[model.MeasurementTypeEnum] | None = None
) -> list[model.TrixelMap]:
    """
    Get the number of sensors per type for a trixel from the DB.

    :param trixel_id: id of the trixel in question
    :param types: optional list of types which restrict results
    :returns: list of TrixelMap entries for the given id
    :raises ValueError: if the trixel id is invalid
    """
    try:
        HTM.get_level(trixel_id)
    except Exception:
        raise ValueError(f"Invalid trixel id: {trixel_id}")

    types = [type.value for type in types] if types is not None else [enum.value for enum in model.MeasurementTypeEnum]

    query = select(model.TrixelMap).where(
        model.TrixelMap.id == trixel_id,
        model.TrixelMap.type_id == model.MeasurementType.id,
        model.MeasurementType.name.in_(types),
        model.TrixelMap.sensor_count > 0,
    )
    return (await db.execute(query)).scalars().all()


async def get_trixel_ids(
    db: AsyncSession,
    trixel_id: int | None = None,
    types: list[model.MeasurementTypeEnum] | None = None,
    limit: PositiveInt = 100,
    offset: int = 0,
) -> list[int]:
    """Get a list of trixels within the provided region.

    :param trixel_id: root trixel, which is used for retrieval, all root-trixels are used if none is provided
    :param types: optional list of types which restrict results
    :param limit: search result limit
    :param offset: skips the first n results
    :returns: list of trixel_ids
    :raises ValueError: if the trixel id is invalid
    """
    types = [type.value for type in types] if types is not None else [enum.value for enum in model.MeasurementTypeEnum]

    query = (
        select(model.TrixelMap.id, model.LevelLookup)
        .where(and_(model.TrixelMap.id == model.LevelLookup.trixel_id, model.TrixelMap.sensor_count > 0))
        .where(and_(model.TrixelMap.type_id == model.MeasurementType.id, model.MeasurementType.name.in_(types)))
    )

    if trixel_id is not None:
        try:
            level = HTM.get_level(trixel_id)

            # Select all trixels where the ID contains the provided trixel_id as a prefix
            query = query.where(model.LevelLookup.level >= level).where(
                model.TrixelMap.id.bitwise_rshift((model.LevelLookup.level - level) * 2) == trixel_id
            )
        except ValueError:
            raise ValueError(f"Invalid trixel id: {trixel_id}")

    query = query.distinct().offset(offset=offset).limit(limit=limit)

    result = (await db.execute(query)).scalars().all()
    return result


async def get_responsible_tms(db: AsyncSession, trixel_id: int) -> TrixelManagementServer | None:
    """
    Get the TMS responsible for the provided Trixel.

    :param trixel_id: The trixel for which the TMS is determined.
    :returns: responsible TrixelManagementServer or None if not present
    :raises ValueError: if the provided trixel_id is invalid
    """
    try:
        level = HTM.get_level(trixel_id)

        # Generate comparison with all parent trixels
        clauses = list()
        for i in range(0, level + 1):
            clauses.append(TMSDelegation.trixel_id == (trixel_id >> i * 2))

        # Select TMS with the highest level which matches the trixel
        query = (
            select(TrixelManagementServer)
            .join(
                TMSDelegation,
                and_(
                    TrixelManagementServer.id == TMSDelegation.tms_id,
                    TrixelManagementServer.active == True,  # noqa: E712
                    TMSDelegation.exclude == False,  # noqa: E712
                ),
            )
            .where(or_(*clauses))
            .join(model.LevelLookup, model.LevelLookup.trixel_id == TMSDelegation.trixel_id)
            .order_by(desc(model.LevelLookup.level))
            .limit(1)
        )

        return (await db.execute(query)).scalar_one_or_none()

    except ValueError:
        raise ValueError(f"Invalid trixel id: {trixel_id}")


async def does_tms_own_trixels(db: AsyncSession, tms_id: int, trixel_ids: set[int]) -> bool:
    """
    Determine if a given set of trixel IDs is delegated to a TMS.

    :param tms_id: The identifier of the TMS
    :param trixel_ids: A set of trixel identifiers.
    :returns: True if all trixels are owned by the TMS, False otherwise
    :raises ValueError: if the provided trixel_id is invalid
    """
    for trixel_id in trixel_ids:
        responsible_tms: TrixelManagementServer | None = await get_responsible_tms(db, trixel_id)
        if responsible_tms is None or responsible_tms.id != tms_id:
            return False
    return True

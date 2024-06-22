"""Global database wrappers."""

from pydantic import PositiveInt
from pynyhtm import HTM
from sqlalchemy import and_, desc, or_, update
from sqlalchemy.orm import Session

import model
from trixel_management.model import TMSDelegation, TrixelManagementServer


def add_level_lookup(db: Session, lookup: dict[int, int]):
    """Insert an entry within the level lookup table.

    Adds all non-existent entries. Does not commit changes.

    :param lookup: dict containing the level for each trixel
    :param level: level at which the trixel is located
    """
    clauses = list()
    for trixel_id in lookup.keys():
        clauses.append(model.LevelLookup.trixel_id == trixel_id)

    existing_trixels = db.query(model.LevelLookup.trixel_id).where(or_(*clauses)).all()

    new_trixels = lookup.keys() - set([x[0] for x in existing_trixels])
    for trixel_id in new_trixels:
        db.add(model.LevelLookup(trixel_id=trixel_id, level=lookup[trixel_id]))


def create_trixel_map(db: Session, trixel_id: int, type_: model.MeasurementType, sensor_count: int) -> model.TrixelMap:
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

        trixel = model.TrixelMap(id=trixel_id, type_=type_, sensor_count=sensor_count)
        db.add(trixel)
        add_level_lookup(db, {trixel_id: level})
        db.commit()

        return trixel

    except ValueError:
        raise ValueError(f"Invalid trixel id: {trixel_id}")


def update_trixel_map(
    db: Session, trixel_id: int, type_: model.MeasurementType, sensor_count: int
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
        .where(model.TrixelMap.id == trixel_id)
        .where(model.TrixelMap.type_ == type_)
        .values(sensor_count=sensor_count)
    )

    result = db.execute(stmt)
    if result.rowcount == 0:
        db.rollback()
        return None

    db.commit()

    return model.TrixelMap(id=trixel_id, type_=type_, sensor_count=sensor_count)


def upsert_trixel_map(db: Session, trixel_id: int, type_: model.MeasurementType, sensor_count: int) -> model.TrixelMap:
    """
    Update or insert into the trixel map if not present.

    :param trixel_id: id of the trixel in question
    :param type_: measurement type
    :param sensor_count: new value
    :return: updated/inserted trixel
    """
    if trixel := update_trixel_map(db, trixel_id, type_, sensor_count):
        return trixel
    else:
        return create_trixel_map(db, trixel_id, type_, sensor_count)


def get_trixel_map(
    db: Session, trixel_id: int, types: list[model.MeasurementType] | None = None
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

    types = types if types is not None else [enum.value for enum in model.MeasurementType]

    return (
        db.query(model.TrixelMap)
        .where(
            and_(
                model.TrixelMap.id == trixel_id,
                model.TrixelMap.type_.in_(types),
                model.TrixelMap.sensor_count > 0,
            )
        )
        .all()
    )


def get_trixel_ids(
    db: Session,
    trixel_id: int | None = None,
    types: list[model.MeasurementType] | None = None,
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
    types = types if types is not None else [enum.value for enum in model.MeasurementType]

    query = (
        db.query(model.TrixelMap.id, model.LevelLookup)
        .where(and_(model.TrixelMap.id == model.LevelLookup.trixel_id, model.TrixelMap.sensor_count > 0))
        .where(model.TrixelMap.type_.in_(types))
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

    result = query.distinct().offset(offset=offset).limit(limit=limit).all()
    return [x[0] for x in result]


def get_responsible_tms(db: Session, trixel_id: int) -> TrixelManagementServer | None:
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
            db.query(TrixelManagementServer)
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
        )

        return query.first()

    except ValueError:
        raise ValueError(f"Invalid trixel id: {trixel_id}")

"""Global database wrappers."""

from pynyhtm import HTM
from sqlalchemy import and_, update
from sqlalchemy.orm import Session

import model


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
        HTM.get_level(trixel_id)
    except Exception:
        raise ValueError(f"Invalid trixel id: {trixel_id}")

    trixel = model.TrixelMap(id=trixel_id, type_=type_, sensor_count=sensor_count)
    db.add(trixel)
    db.commit()
    return trixel


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
        db.query(model.TrixelMap).where(and_(model.TrixelMap.id == trixel_id, model.TrixelMap.type_.in_(types))).all()
    )

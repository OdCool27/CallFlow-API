from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/calls", tags=["Calls"])


def filtered_calls(db, agent_id=None, extension=None, start=None, end=None):
    query = db.query(models.Call)
    if agent_id is not None:
        query = query.filter(models.Call.agent_id == agent_id)
    if extension:
        channel_call_ids = db.query(models.CallChannel.call_id).filter(models.CallChannel.extension == extension)
        query = query.filter(or_(models.Call.from_extension == extension, models.Call.to_extension == extension,
                                 models.Call.id.in_(channel_call_ids)))
    # Date ranges refer to call start, UTC, inclusive start and exclusive end.
    def utc(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if start and end and utc(start) >= utc(end):
        raise HTTPException(422, "start must be before end")
    if start:
        query = query.filter(models.Call.started_at >= utc(start))
    if end:
        query = query.filter(models.Call.started_at < utc(end))
    return query


@router.post("", status_code=409)
def create_call():
    raise HTTPException(409, "Calls are created by Asterisk AMI events. Dial a registered SIP endpoint.")


@router.get("", response_model=list[schemas.CallResponse])
def get_calls(status: str | None = None, agent_id: int | None = None, extension: str | None = None,
              start: datetime | None = None, end: datetime | None = None,
              limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    query = filtered_calls(db, agent_id, extension, start, end)
    if status:
        query = query.filter(models.Call.status == status.upper())
    return query.order_by(models.Call.started_at.desc(), models.Call.id.desc()).offset(offset).limit(limit).all()


@router.get("/active", response_model=list[schemas.CallResponse])
def active_calls(db: Session = Depends(get_db)):
    return db.query(models.Call).filter(models.Call.source == "AMI", models.Call.ended_at.is_(None)).all()


@router.get("/{call_id}", response_model=schemas.CallResponse)
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = db.get(models.Call, call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    return call


@router.patch("/{call_id}", response_model=schemas.CallResponse)
def update_call(call_id: int, update: schemas.CallUpdate, db: Session = Depends(get_db)):
    call = get_call(call_id, db)
    changes = update.model_dump(exclude_unset=True)
    if changes.get("customer_id") is not None and db.get(models.Customer, changes["customer_id"]) is None:
        raise HTTPException(404, "Customer not found")
    for name, value in changes.items():
        setattr(call, name, value)
    db.commit()
    db.refresh(call)
    return call


@router.delete("/{call_id}", status_code=204)
def delete_call(call_id: int, db: Session = Depends(get_db)):
    call = get_call(call_id, db)
    if call.source == "AMI":
        raise HTTPException(409, "AMI call history is retained for event correlation")
    db.delete(call)
    db.commit()

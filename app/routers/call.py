from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/calls",
    tags=["Calls"]
)

#Post a Call
@router.post(
    "",
    response_model=schemas.CallResponse,
    status_code=201
)
def create_call(
        call: schemas.CallCreate,
        db: Session = Depends(get_db),
):
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == call.customer_id)
        .first()
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == call.agent_id)
        .first()
    )


    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    direction = call.direction.upper()

    if direction not in ["INBOUND", "OUTBOUND"]:
        raise HTTPException(
            status_code=400,
            detail="Direction must be INBOUND or OUTBOUND"
        )

    new_call = models.Call(
        customer_id=call.customer_id,
        agent_id=call.agent_id,
        direction=direction,
        status="IN_PROGRESS",
        started_at=datetime.now(timezone.utc),
        notes=call.notes
    )

    db.add(new_call)
    db.commit()
    db.refresh(new_call)

    return new_call

#Get all Calls w/ Query Parameters included
@router.get(
    "",
    response_model=list[schemas.CallResponse]
)
def get_calls(
    status: str | None = None,
    agent_id: int | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Call)

    if status:
        query = query.filter(
            models.Call.status == status.upper()
        )

    if agent_id:
        query = query.filter(
            models.Call.agent_id == agent_id
        )

    return query.all()



#Get a single call
@router.get(
    "/{call_id}",
    response_model=schemas.CallResponse
)
def get_call(
    call_id: int,
    db: Session = Depends(get_db)
):
    call = (
        db.query(models.Call)
        .filter(models.Call.id == call_id)
        .first()
    )

    if call is None:
        raise HTTPException(
            status_code=404,
            detail="Call not found"
        )

    return call


#Update a Call
@router.patch(
    "/{call_id}",
    response_model=schemas.CallResponse
)
def update_call(
        call_id: int,
        call_update: schemas.CallUpdate,
        db: Session = Depends(get_db)
):
    call = (
        db.query(models.Call)
        .filter(models.Call.id == call_id)
        .first()
    )

    if call is None:
        raise HTTPException(
            status_code=404,
            detail="Call not found"
        )

    if call_update.status is not None:
        status = call_update.status.upper()

        allowed_statuses = ["IN_PROGRESS", "COMPLETED", "MISSED", "FAILED"]

        if status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Status must be one of {allowed_statuses}"
            )

        call.status = status


    if call_update.ended_at is not None:
        started_at = call.started_at
        ended_at = call_update.ended_at

        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        if ended_at.tzinfo is None:
            ended_at = ended_at.replace(tzinfo=timezone.utc)

        if ended_at < started_at:
            raise HTTPException(
                status_code=400,
                detail="Call end time cannot be before start time"
            )

        call.ended_at = call_update.ended_at

    if call_update.notes is not None:
        call.notes = call_update.notes

    db.commit()
    db.refresh(call)

    return call


#Delete a Call
@router.delete(
    "/{call_id}",
    status_code=204
)
def delete_call(
    call_id: int,
    db: Session = Depends(get_db)
):
    call = (
        db.query(models.Call)
        .filter(models.Call.id == call_id)
        .first()
    )

    if call is None:
        raise HTTPException(
            status_code=404,
            detail="Call not found"
        )

    db.delete(call)
    db.commit()
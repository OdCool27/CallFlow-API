from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas


router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


@router.get("/agents")
def get_agent_call_summary(
    db: Session = Depends(get_db)
):
    results = (
        db.query(
            models.Agent.id,
            models.Agent.name,
            func.count(models.Call.id).label("total_calls")
        )
        .outerjoin(
            models.Call,
            models.Agent.id == models.Call.agent_id
        )
        .group_by(
            models.Agent.id,
            models.Agent.name
        )
        .all()
    )

    return [
        {
            "agent_id": row.id,
            "agent_name": row.name,
            "total_calls": row.total_calls
        }
        for row in results
    ]


@router.get(
    "/agents/{agent_id}/statistics",
    response_model=schemas.AgentStatisticsResponse
)
def get_agent_statistics(
    agent_id: int,
    db: Session = Depends(get_db)
):
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == agent_id)
        .first()
    )

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    statistics = (
        db.query(
            func.count(models.Call.id).label("total_calls"),

            func.sum(
                case(
                    (models.Call.status == "COMPLETED", 1),
                    else_=0
                )
            ).label("completed_calls"),

            func.avg(
                case(
                    (
                        models.Call.ended_at.isnot(None),
                        func.strftime("%s", models.Call.ended_at)
                        -
                        func.strftime("%s", models.Call.started_at)
                    ),
                    else_=None
                )
            ).label("average_duration")
        )
        .filter(models.Call.agent_id == agent_id)
        .first()
    )

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "total_calls": statistics.total_calls or 0,
        "completed_calls": statistics.completed_calls or 0,
        "average_call_duration_seconds": statistics.average_duration
    }
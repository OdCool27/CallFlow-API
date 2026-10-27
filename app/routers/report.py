from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.routers.call import filtered_calls

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/agents")
def get_agent_call_summary(db: Session = Depends(get_db)):
    results = (db.query(models.Agent.id, models.Agent.name, func.count(models.Call.id).label("total_calls"))
               .outerjoin(models.Call, models.Agent.id == models.Call.agent_id)
               .group_by(models.Agent.id, models.Agent.name).all())
    return [{"agent_id": r.id, "agent_name": r.name, "total_calls": r.total_calls} for r in results]


def statistics(query):
    calls = query.subquery()
    # Exclude legacy/incomplete samples from duration averages: their connection time is unknown.
    count, completed, average = query.session.query(
        func.count(calls.c.id),
        func.sum(case((calls.c.status == "COMPLETED", 1), else_=0)),
        func.avg(case(((calls.c.answered_at.isnot(None) & calls.c.ended_at.isnot(None)
                        & (calls.c.tracking_incomplete == False)), calls.c.connected_seconds), else_=None))
    ).one()
    return {"total_calls": count, "completed_calls": completed or 0, "average_call_duration_seconds": average}


@router.get("/agents/{agent_id}/statistics", response_model=schemas.AgentStatisticsResponse)
def get_agent_statistics(agent_id: int, start: datetime | None = None, end: datetime | None = None,
                         db: Session = Depends(get_db)):
    agent = db.get(models.Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return {"agent_id": agent.id, "agent_name": agent.name,
            **statistics(filtered_calls(db, agent_id=agent_id, start=start, end=end))}


@router.get("/calls")
def call_statistics(start: datetime | None = None, end: datetime | None = None,
                    agent_id: int | None = None, extension: str | None = None, db: Session = Depends(get_db)):
    query = filtered_calls(db, agent_id, extension, start, end)
    grouped = query.with_entities(models.Call.status, func.count(models.Call.id)).group_by(models.Call.status).all()
    return {**statistics(query), "by_status": {status: count for status, count in grouped}}

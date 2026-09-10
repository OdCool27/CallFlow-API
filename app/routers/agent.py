from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/agent",
    tags=["Agent"]
)

@router.post(
    "",
    response_model=schemas.AgentResponse,
    status_code=201
)
def create_agent(
        agent: schemas.AgentCreate,
        db: Session = Depends(get_db),
):
    existing_agent = (
        db.query(models.Agent)
        .filter(models.Agent.extension == agent.extension)
        .first()
    )

    if existing_agent:
        raise HTTPException(
            status_code=409,
            detail="An agent with this extension already exists"
        )

    new_agent = models.Agent(
        name=agent.name,
        extension=agent.extension,
        department=agent.department
    )

    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    return new_agent


@router.get(
    "",
    response_model=list[schemas.AgentResponse]
)
def get_agents(
        db: Session = Depends(get_db)
):
    return db.query(models.Agent).all()


@router.get(
    "/{agent_id}",
    response_model=schemas.AgentResponse
)
def get_agent(
        agent_id: int,
        db:Session = Depends(get_db)
):
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == agent_id)
        .first()
    )

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="An agent with this id does not exist"
        )
    return agent
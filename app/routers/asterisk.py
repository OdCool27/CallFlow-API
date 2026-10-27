from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Endpoint
from app.schemas import AMIStatus, EndpointResponse

router = APIRouter(prefix="/asterisk", tags=["Asterisk"])


@router.get("/status", response_model=AMIStatus)
def status(request: Request):
    return request.app.state.ami.status()


@router.get("/endpoints", response_model=list[EndpointResponse])
def endpoints(request: Request, db: Session = Depends(get_db)):
    ami = request.app.state.ami
    fresh = ami.connected and ami.synchronized
    agents = {a.extension: a.id for a in db.query(Agent).all()}
    observed = {e.extension: e for e in db.query(Endpoint).all()}
    result = []
    for ext in sorted(set(agents) | set(observed)):
        endpoint = observed.get(ext)
        contact = endpoint.contact_status if endpoint and fresh else "UNKNOWN"
        device = endpoint.device_state if endpoint and fresh else "UNKNOWN"
        result.append({"extension": ext, "agent_id": agents.get(ext), "contact_status": contact,
                       "device_state": device, "updated_at": endpoint.updated_at if endpoint else None,
                       "stale": not fresh or endpoint is None,
                       "available": contact in {"Reachable", "Created", "Avail", "Available"} and device == "NOT_INUSE"})
    return result

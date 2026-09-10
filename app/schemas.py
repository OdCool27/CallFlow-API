from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    phone_number: str
    email: str | None = None


class CustomerResponse(CustomerCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AgentCreate(BaseModel):
    name: str
    extension: str
    department: str | None = None


class AgentResponse(AgentCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CallCreate(BaseModel):
    customer_id: int
    agent_id: int
    direction: str
    started_at : datetime
    notes: str | None = None


class CallUpdate(BaseModel):
    status: str | None = None
    ended_at: datetime | None = None
    notes: str | None = None

class CallResponse(BaseModel):
    id: int
    customer_id: int
    agent_id: int
    direction: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)
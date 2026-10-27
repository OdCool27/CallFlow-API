from datetime import datetime
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=30)
    email: str | None = None


class CustomerResponse(CustomerCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    extension: str = Field(pattern=r"^[0-9]{1,20}$")
    department: str | None = Field(default=None, max_length=100)


class AgentResponse(AgentCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CallUpdate(BaseModel):
    # PBX state is authoritative. Customer association remains an application decision.
    model_config = ConfigDict(extra="forbid")
    customer_id: int | None = None
    notes: str | None = Field(default=None, max_length=10000)


class CallResponse(BaseModel):
    id: int
    customer_id: int | None
    agent_id: int | None
    direction: str
    status: str
    source: str
    linked_id: str | None
    from_extension: str | None
    to_extension: str | None
    started_at: datetime
    ringing_at: datetime | None
    answered_at: datetime | None
    connected_at: datetime | None
    ended_at: datetime | None
    setup_seconds: float | None
    ringing_seconds: float | None
    connected_seconds: float = Field(validation_alias=AliasChoices("measured_connected_seconds", "connected_seconds"))
    total_seconds: float | None
    disposition: str | None
    tracking_incomplete: bool
    notes: str | None
    model_config = ConfigDict(from_attributes=True)


class AgentStatisticsResponse(BaseModel):
    agent_id: int
    agent_name: str
    total_calls: int
    completed_calls: int
    average_call_duration_seconds: float | None


class AMIStatus(BaseModel):
    enabled: bool
    connected: bool
    synchronized: bool
    state: str
    attempts: int
    last_event_at: datetime | None


class EndpointResponse(BaseModel):
    extension: str
    contact_status: str
    device_state: str
    updated_at: datetime | None
    agent_id: int | None = None
    available: bool
    stale: bool

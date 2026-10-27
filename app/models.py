from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base

class Customer(Base):
    __tablename__= "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String(30), nullable=False)
    email = Column(String, nullable=True)

    calls = relationship("Call", back_populates="customer")


class Agent(Base):
    __tablename__= "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    extension = Column(String(20), unique=True, nullable=False)
    department = Column(String(100), nullable=False)

    calls = relationship("Call", back_populates="agent")

class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    direction = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="IN_PROGRESS")

    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)
    source = Column(String(20), nullable=False, default="AMI")
    linked_id = Column(String(150), unique=True, nullable=True)
    from_extension = Column(String(80), nullable=True, index=True)
    to_extension = Column(String(80), nullable=True, index=True)
    ringing_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, nullable=True)
    connected_seconds = Column(Float, nullable=False, default=0)
    connection_open_at = Column(DateTime, nullable=True)
    setup_seconds = Column(Float, nullable=True)
    ringing_seconds = Column(Float, nullable=True)
    total_seconds = Column(Float, nullable=True)
    disposition = Column(String(30), nullable=True)
    tracking_incomplete = Column(Boolean, nullable=False, default=False)


    customer = relationship("Customer", back_populates="calls")
    agent = relationship("Agent", back_populates="calls")
    channels = relationship("CallChannel", back_populates="call", cascade="all, delete-orphan")

    @property
    def measured_connected_seconds(self):
        elapsed = self.connected_seconds or 0
        if self.connection_open_at and self.ended_at is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            elapsed += max(0, (now - self.connection_open_at).total_seconds())
        return elapsed


class CallChannel(Base):
    __tablename__ = "call_channels"
    unique_id = Column(String(150), primary_key=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    extension = Column(String(80), nullable=True)
    ended_at = Column(DateTime, nullable=True)
    bridge_id = Column(String(150), nullable=True, index=True)
    call = relationship("Call", back_populates="channels")


class Endpoint(Base):
    __tablename__ = "endpoints"
    extension = Column(String(80), primary_key=True)
    contact_status = Column(String(40), nullable=False, default="UNKNOWN")
    device_state = Column(String(40), nullable=False, default="UNKNOWN")
    updated_at = Column(DateTime, nullable=False)

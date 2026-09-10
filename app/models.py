from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

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
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    direction = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, default="IN_PROGRESS")

    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)

    notes = Column(Text, nullable=True)


    customer = relationship("Customer", back_populates="calls")
    agent = relationship("Agent", back_populates="calls")

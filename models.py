import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (Boolean, Column, DateTime, Integer, String, Text,
                        create_engine)
from sqlalchemy.orm import Session, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///followup.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
Base = declarative_base()


def utcnow():
    """Naive UTC timestamp (avoids aware/naive comparison issues with SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True)
    name = Column(String)
    phone = Column(String, unique=True, nullable=False)
    language = Column(String, default="en")
    opted_out = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    last_contact = Column(DateTime, default=utcnow)


class FollowUp(Base):
    __tablename__ = "followups"

    id = Column(String, primary_key=True)
    patient_phone = Column(String, nullable=False)
    patient_name = Column(String)
    ftype = Column(String)              # consultation | scan | beta_hcg | post_transfer
    due_date = Column(String)           # YYYY-MM-DD
    status = Column(String, default="pending")  # pending|reminded|confirmed|missed|completed
    attempts = Column(Integer, default=0)
    awaiting_date = Column(Boolean, default=False)
    last_reminded_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(String, primary_key=True)
    patient_phone = Column(String)
    direction = Column(String)          # inbound | outbound
    channel = Column(String)            # whatsapp
    message = Column(Text)
    action_taken = Column(String)
    created_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    event_type = Column(String)         # reminder|retry|escalation|missed|confirm|reschedule|complete|create|opt_out
    patient_phone = Column(String)
    description = Column(Text)
    decided_by = Column(String, default="system")
    outcome = Column(String)
    created_at = Column(DateTime, default=utcnow)


def log_message(session: Session, phone, direction, channel, message, action=""):
    session.add(MessageLog(id=generate_id("msg"), patient_phone=phone,
                           direction=direction, channel=channel,
                           message=message, action_taken=action))
    session.commit()


def log_audit(session: Session, event_type, phone, description,
              decided_by="system", outcome=""):
    session.add(AuditLog(id=generate_id("aud"), event_type=event_type,
                         patient_phone=phone, description=description,
                         decided_by=decided_by, outcome=outcome))
    session.commit()


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print(f"Tables created in {DATABASE_URL}")
    print("Tables: patients, followups, message_logs, audit_logs")

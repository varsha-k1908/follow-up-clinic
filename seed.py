"""Seed demo patients and follow-ups for the live demo.

Usage:
    python seed.py                 # uses DEMO_PHONE from .env
    python seed.py +919812345678   # override the demo phone number
    python seed.py --reset         # wipe the database first
"""
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import Base, FollowUp, Patient, engine, generate_id

load_dotenv()

args = [a for a in sys.argv[1:] if not a.startswith("--")]
DEMO_PHONE = os.getenv("DEMO_PHONE") or (args[0] if args else "+919999999999")


def add_patient(session, phone, name, language="en"):
    p = session.query(Patient).filter(Patient.phone == phone).first()
    if not p:
        p = Patient(id=generate_id("pat"), phone=phone, name=name, language=language)
        session.add(p)
        session.commit()
    return p


def add_followup(session, phone, name, ftype, due):
    fu = FollowUp(id=generate_id("fu"), patient_phone=phone, patient_name=name,
                  ftype=ftype, due_date=due)
    session.add(fu)
    session.commit()
    return fu


def main():
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
        print("Database reset.")
    Base.metadata.create_all(engine)

    today = date.today()
    with Session(engine) as session:
        # The number you will demo with (must be a WhatsApp number you control)
        add_patient(session, DEMO_PHONE, "Asha Rao", "en")
        add_followup(session, DEMO_PHONE, "Asha Rao", "scan",
                     (today - timedelta(days=3)).isoformat())
        add_followup(session, DEMO_PHONE, "Asha Rao", "beta_hcg",
                     today.isoformat())
        add_followup(session, DEMO_PHONE, "Asha Rao", "consultation",
                     (today + timedelta(days=2)).isoformat())
        add_followup(session, DEMO_PHONE, "Asha Rao", "post_transfer",
                     (today + timedelta(days=6)).isoformat())

        # Extra patients so the dashboard looks realistic
        add_patient(session, "+919000000101", "Priya Sharma", "hi")
        add_followup(session, "+919000000101", "Priya Sharma", "scan",
                     (today - timedelta(days=1)).isoformat())
        add_followup(session, "+919000000101", "Priya Sharma", "consultation",
                     (today + timedelta(days=4)).isoformat())

        add_patient(session, "+919000000102", "Meena Patil", "mr")
        add_followup(session, "+919000000102", "Meena Patil", "beta_hcg",
                     today.isoformat())
        add_followup(session, "+919000000102", "Meena Patil", "post_transfer",
                     (today + timedelta(days=9)).isoformat())

    print("Seeded demo data.")
    print(f"Demo patient number: {DEMO_PHONE}")


if __name__ == "__main__":
    main()

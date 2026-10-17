"""WhatsApp sending, message templates, and the reminder / retry / escalation jobs."""
import json
import os
import re
from datetime import date

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import (FollowUp, Patient, engine, log_audit, log_message,
                    utcnow)

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ESCALATION_WHATSAPP = os.getenv("ESCALATION_WHATSAPP")
SEND_REAL = os.getenv("SEND_REAL_WHATSAPP", "true").strip().lower() == "true"
RETRY_MINUTES = int(os.getenv("RETRY_MINUTES", "60"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "2"))

TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID", "").strip()
try:
    _cv = os.getenv("TWILIO_CONTENT_VARS", "").strip()
    CONTENT_VAR_MAP = json.loads(_cv) if _cv else {}
except Exception:
    CONTENT_VAR_MAP = {}

try:
    with open("knowledge_base.json", "r", encoding="utf-8") as f:
        KB = json.load(f)
except Exception:
    KB = {"clinic_name": "Fertility Clinic", "followup_types": {}}

CLINIC_NAME = KB.get("clinic_name", "Fertility Clinic")
FTYPE = KB.get("followup_types", {})

TEMPLATES = {
    "en": ("Hello {name}, this is {clinic}. Reminder: your {ftype} is due on {date}. "
           "Reply CONFIRM to confirm, or RESCHEDULE to change the date."),
    "hi": ("नमस्ते {name}, {clinic} की ओर से। याद दिलाना चाहते हैं कि आपका {ftype} "
           "{date} को है। पुष्टि के लिए CONFIRM लिखें, तारीख बदलने के लिए RESCHEDULE लिखें।"),
    "mr": ("नमस्कार {name}, {clinic} मधून. स्मरण: तुमचे {ftype} {date} रोजी आहे. "
           "पुष्टीसाठी CONFIRM लिहा, तारीख बदलण्यासाठी RESCHEDULE लिहा."),
}


def normalize_phone(raw):
    """Return an E.164 number. Bare 10-digit numbers default to India (+91)."""
    if not raw:
        return raw
    s = re.sub(r"[\s()\-]", "", str(raw).strip())
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        s = ("+91" + s) if re.fullmatch(r"\d{10}", s) else ("+" + s)
    return s


_PLACEHOLDER_SIDS = {"ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", ""}

LAST_ERROR = None


def twilio_configured():
    """True only when real-looking Twilio credentials are present."""
    return bool(
        TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER
        and TWILIO_ACCOUNT_SID not in _PLACEHOLDER_SIDS
        and TWILIO_ACCOUNT_SID.startswith("AC")
        and TWILIO_AUTH_TOKEN not in ("your_auth_token", "")
        and not TWILIO_WHATSAPP_NUMBER.endswith("XXXXXXXXXX")
    )


def send_whatsapp(to, body):
    """Send a WhatsApp message via Twilio. Returns True only if actually sent."""
    global LAST_ERROR
    LAST_ERROR = None
    if not to:
        LAST_ERROR = "no destination number"
        return False
    to = normalize_phone(to)
    if not SEND_REAL:
        print(f"[whatsapp:simulated] -> {to}: {body}")
        return True
    if not twilio_configured():
        LAST_ERROR = "Twilio credentials missing/placeholders in .env"
        print("[whatsapp:warning] Twilio credentials are missing/placeholders in .env "
              "-- not sending. Message below was NOT delivered:")
        print(f"[whatsapp:not-sent] -> {to}: {body}")
        return False
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={
                    "From": f"whatsapp:{normalize_phone(TWILIO_WHATSAPP_NUMBER)}",
                    "To": f"whatsapp:{to}",
                    "Body": body,
                },
            )
        if r.status_code >= 300:
            LAST_ERROR = f"{r.status_code}: {r.text[:300]}"
            print(f"[whatsapp:error] {LAST_ERROR}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        LAST_ERROR = str(e)
        print(f"[whatsapp:error] {e}")
        return False


_CONTENT_FIELDS = {
    "name": lambda fu, patient: (patient.name if patient else "there"),
    "date": lambda fu, patient: (fu.due_date if fu else ""),
    "ftype": lambda fu, patient: (FTYPE.get(fu.ftype, (fu.ftype or "follow-up").replace("_", " "))
                                  if fu else ""),
    "clinic": lambda fu, patient: CLINIC_NAME,
    "phone": lambda fu, patient: (fu.patient_phone if fu else ""),
}


def build_content_variables(fu, patient):
    """Map our data into the template's numbered placeholders (see TWILIO_CONTENT_VARS)."""
    mapping = CONTENT_VAR_MAP or {"1": "date", "2": "ftype"}
    out = {}
    for slot, field in mapping.items():
        fn = _CONTENT_FIELDS.get(field)
        out[str(slot)] = fn(fu, patient) if fn else ""
    return out


def send_template(to, variables, content_sid=None):
    """Send a pre-approved Content template (required on Twilio trial accounts)."""
    global LAST_ERROR
    LAST_ERROR = None
    sid = content_sid or TWILIO_CONTENT_SID
    if not to:
        LAST_ERROR = "no destination number"
        return False
    if not sid:
        LAST_ERROR = "TWILIO_CONTENT_SID not set"
        return False
    if not twilio_configured():
        LAST_ERROR = "Twilio credentials missing/placeholders in .env"
        print("[whatsapp:not-sent] Twilio not configured; template not sent.")
        return False
    to = normalize_phone(to)
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                data={
                    "From": f"whatsapp:{normalize_phone(TWILIO_WHATSAPP_NUMBER)}",
                    "To": f"whatsapp:{to}",
                    "ContentSid": sid,
                    "ContentVariables": json.dumps(variables),
                },
            )
        if r.status_code >= 300:
            LAST_ERROR = f"{r.status_code}: {r.text[:300]}"
            print(f"[whatsapp:error] {LAST_ERROR}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        LAST_ERROR = str(e)
        print(f"[whatsapp:error] {e}")
        return False


def reminder_message(fu, patient):
    lang = (patient.language or "en") if patient else "en"
    template = TEMPLATES.get(lang, TEMPLATES["en"])
    ftype = FTYPE.get(fu.ftype, (fu.ftype or "follow-up").replace("_", " "))
    return template.format(name=(patient.name if patient else "there"),
                           clinic=CLINIC_NAME, ftype=ftype, date=fu.due_date)


def send_reminder(session, fu, patient):
    if TWILIO_CONTENT_SID:
        variables = build_content_variables(fu, patient)
        ok = send_template(fu.patient_phone, variables)
        msg = f"[template {TWILIO_CONTENT_SID}] {json.dumps(variables)}"
    else:
        msg = reminder_message(fu, patient)
        ok = send_whatsapp(fu.patient_phone, msg)
    log_message(session, fu.patient_phone, "outbound", "whatsapp", msg, "reminder")
    return ok


def send_escalation(phone, reason, last_message=""):
    body = (f"STAFF ALERT: patient {phone} has not responded ({reason}).\n"
            f"Last message: {last_message or 'n/a'}\nPlease follow up manually.")
    print(body)
    if ESCALATION_WHATSAPP:
        send_whatsapp(ESCALATION_WHATSAPP, body)
    return True


def run_daily_reminders():
    """Send first reminders for every follow-up that is due today or overdue."""
    today = date.today().isoformat()
    sent = 0
    with Session(engine) as session:
        due = session.query(FollowUp).filter(
            FollowUp.status == "pending",
            FollowUp.due_date <= today,
        ).order_by(FollowUp.due_date.asc()).all()

        for fu in due:
            patient = session.query(Patient).filter(
                Patient.phone == fu.patient_phone).first()
            if patient and patient.opted_out:
                continue
            send_reminder(session, fu, patient)
            fu.status = "reminded"
            fu.attempts = 1
            fu.last_reminded_at = utcnow()
            fu.updated_at = utcnow()
            log_audit(session, "reminder", fu.patient_phone,
                      f"Reminder sent for {fu.ftype} due {fu.due_date}")
            session.commit()
            sent += 1
    return sent


def run_retry_escalation(force=False):
    """Retry non-responders, then mark missed and escalate to staff."""
    now = utcnow()
    retried = 0
    missed = 0
    with Session(engine) as session:
        reminded = session.query(FollowUp).filter(
            FollowUp.status == "reminded").all()

        for fu in reminded:
            if fu.last_reminded_at is None:
                continue
            elapsed = (now - fu.last_reminded_at).total_seconds() / 60.0
            if not force and elapsed < RETRY_MINUTES:
                continue

            patient = session.query(Patient).filter(
                Patient.phone == fu.patient_phone).first()

            if fu.attempts < MAX_ATTEMPTS:
                send_reminder(session, fu, patient)
                fu.attempts += 1
                fu.last_reminded_at = now
                fu.updated_at = now
                log_audit(session, "retry", fu.patient_phone,
                          f"Retry #{fu.attempts} for {fu.ftype} due {fu.due_date}")
                session.commit()
                retried += 1
            else:
                fu.status = "missed"
                fu.updated_at = now
                log_audit(session, "missed", fu.patient_phone,
                          f"No response after {fu.attempts} attempts for {fu.ftype}")
                send_escalation(fu.patient_phone, "no response to reminders")
                log_audit(session, "escalation", fu.patient_phone,
                          "Escalated to staff after missed follow-up")
                session.commit()
                missed += 1
    return {"retried": retried, "missed": missed}

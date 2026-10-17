# Fertility Clinic Follow-up Manager

Hackathon prototype for **Problem 1: Patient Follow-up Management**.

Tracks every patient's follow-up dates, shows staff a self-building "calls for
today" list (most overdue first), sends WhatsApp reminders in the patient's
language, lets patients **confirm** or **reschedule** by reply, retries
non-responders, escalates to staff, and reports weekly completed / missed /
rescheduled counts.

Built by adapting the architecture of
[`mbuguacessy-glitch/mediflow-ai-receptionist`](https://github.com/mbuguacessy-glitch/mediflow-ai-receptionist)
(FastAPI + SQLAlchemy + Twilio WhatsApp). The LLM brain was replaced with a
fast, dependency-free **rule-based** reply parser so no API key is needed.

## Stack
- **Backend:** FastAPI + SQLAlchemy (SQLite by default)
- **Messaging:** Twilio WhatsApp sandbox
- **Scheduling:** APScheduler (daily reminders + retry/escalate)
- **UI:** single HTML dashboard (auto-refresh, no build step)

## Project layout
```
followup-clinic/
  app.py                API + staff dashboard
  models.py             Patient, FollowUp, MessageLog, AuditLog
  replies.py            rule-based confirm / reschedule / opt-out parser
  reminders.py          WhatsApp send + reminder/retry/escalation jobs
  seed.py               demo data
  knowledge_base.json   clinic info + follow-up types + message languages
  templates/dashboard.html
  requirements.txt
  .env.example
```

## Setup
Run these from inside `followup-clinic`:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set your Twilio values and staff number:
```
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=+14155238886
ESCALATION_WHATSAPP=+91XXXXXXXXXX
DEMO_PHONE=+91XXXXXXXXXX
```
> Tip: set `SEND_REAL_WHATSAPP=false` to run the whole flow without Twilio —
> messages are printed to the console instead.

## Run
```bat
python seed.py --reset
uvicorn app:app --port 8009
```
Open <http://localhost:8009> for the dashboard.

## Connect real WhatsApp (Twilio sandbox)
1. In the Twilio console open **Messaging > Try it out > Send a WhatsApp message**.
   Each demo phone (including yours) must first send the shown `join <code>` message.
2. Expose your server:
   ```bat
   ngrok http 8009
   ```
3. In the sandbox settings, set **"WHEN A MESSAGE COMES IN"** to:
   ```
   https://<your-ngrok-id>.ngrok-free.app/webhook/whatsapp
   ```
   (method `POST`). Re-paste this whenever ngrok restarts with a new URL.

## Staff dashboard actions
- **Add Patient** — name, WhatsApp number, preferred language
- **Add Follow-Up** — pick a patient, type (consultation / scan / beta hCG / post-transfer), due date
- **Notify** (per row) — instantly sends that follow-up's WhatsApp reminder
- **Reschedule** (per row) — change the due date
- **Done** (per row) — mark completed (moves to History)
- **Send today's reminders** / **Run retry / escalate** — trigger the automation jobs now

## Demo script
1. Start the server, open the dashboard: overdue items are red and on top.
2. Click **Send today's reminders** → the demo WhatsApp number receives a reminder
   in its configured language.
3. Reply **`RESCHEDULE`** on WhatsApp → the bot asks for a date → reply
   **`20 Oct`** (or `tomorrow`). The item moves to the new date and the
   dashboard updates on its own.
4. Reply **`CONFIRM`** for another follow-up → status becomes *confirmed*.
5. Show the weekly stat cards (confirmed / rescheduled / missed / reminders) and
   `GET /audit` for the full trail.
6. Optional: click **Run retry / escalate** to show a non-responder being
   retried and then escalated to the staff number.

Fallback if the network/Twilio misbehaves, simulate a reply locally:
```bat
curl -X POST http://localhost:8009/message -H "Content-Type: application/json" -d "{\"phone\":\"+91XXXXXXXXXX\",\"message\":\"reschedule tomorrow\"}"
```

## Key endpoints
| Method | Path | Purpose |
|---|---|---|
| GET  | `/` | Staff dashboard |
| POST | `/webhook/whatsapp` | Twilio inbound webhook |
| POST | `/message` | Simulate an inbound reply |
| GET  | `/followups/today` | Due + overdue, most overdue first |
| GET  | `/followups/upcoming` | Future follow-ups |
| POST | `/followups` | Create a follow-up |
| POST | `/followups/{id}/complete` | Mark done |
| POST | `/followups/{id}/reschedule` | Change date |
| POST | `/followups/{id}/notify` | Send a reminder for one follow-up now |
| GET  | `/patients` | List patients |
| POST | `/patients` | Add a patient |
| GET  | `/stats/weekly` | Weekly completed/missed/rescheduled/reminders |
| POST | `/reminders/run` | Send today's reminders now |
| POST | `/reminders/retry?force=true` | Retry then escalate |
| GET  | `/audit`, `/messages` | Audit + message logs |
| GET  | `/health` | Health check |

## How the reply rules work (`replies.py`)
- **Confirm:** `confirm, yes, ok, haan, sure, 1, 👍`
- **Reschedule:** `reschedule, change, postpone, no, 2` (+ an optional date in the
  same message, e.g. `reschedule 20 Oct` or `reschedule tomorrow`). If no date is
  given, the follow-up is flagged `awaiting_date` and the bot asks for one.
- **Opt-out:** `stop` (reply `START` to resume).
- Reminders are sent in `en` / `hi` / `mr` based on the patient's stored
  `language`.

## Notes
- SQLite file `followup.db` is created on first run.
- The daily reminder job runs at 08:00 (`TIMEZONE` in `.env`); use the dashboard
  buttons to trigger jobs instantly during the demo.
- Retry policy: `RETRY_MINUTES` (default 60) before a retry, `MAX_ATTEMPTS`
  (default 2) before escalation to `ESCALATION_WHATSAPP`.

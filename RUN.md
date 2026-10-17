# FertiFlow — How to Run (Windows)

Project folder: `C:\Users\varsh\Downloads\Projects\fertiflow`
Login: `admin` / `admin123`
URL: http://localhost:8501

A full Streamlit app for fertility-clinic follow-up automation
(2-day reminder logic, EN/TA/HI messages, retry, escalation, SQLite).
WhatsApp is **click-to-chat** (`wa.me`) — opened manually from the UI.

---

## One-time setup (run once)

Open **Command Prompt** (`cmd`, not PowerShell) and run:

```bat
cd /d C:\Users\varsh\Downloads\Projects\fertiflow
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python database\seed.py
```

## Every time you start the app

```bat
cd /d C:\Users\varsh\Downloads\Projects\fertiflow
.venv\Scripts\activate.bat
streamlit run app.py
```

Streamlit prints and opens http://localhost:8501 automatically.
Stop the server with **Ctrl + C**.

Shortcut: after activating the venv, you can just double-click / run `run.bat`
(it seeds the demo data then starts Streamlit).

## Quick reference

| Task | Command |
| --- | --- |
| Go to project | `cd /d C:\Users\varsh\Downloads\Projects\fertiflow` |
| Activate venv (cmd) | `.venv\Scripts\activate.bat` |
| Activate venv (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Install deps | `pip install -r requirements.txt` |
| Seed demo data | `python database\seed.py` |
| Run app | `streamlit run app.py` |
| Stop app | `Ctrl + C` |

## Reset demo data

```bat
del data\fertiflow.db
python database\seed.py
```

## Notes

- If `python` is not found, try `py -3.13` or `py` instead, or reinstall Python and tick "Add to PATH".
- Optional real Twilio: copy `.env.example` to `.env`, fill in values, set `USE_TWILIO=true`.
  (The shipped demo works without Twilio using click-to-chat links.)

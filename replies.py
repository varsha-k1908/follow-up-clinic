"""Rule-based reply parser — no LLM required."""
from datetime import datetime

from dateutil import parser as dateparser

CONFIRM_WORDS = ["confirm", "confirmed", "yes", "yep", "yeah", "ok", "okay",
                 "haan", "han", "sure", "done", "1", "👍", "✅"]
RESCHEDULE_WORDS = ["reschedule", "re-schedule", "change", "postpone", "postphone",
                    "different", "another", "later", "cant", "can't", "cannot",
                    "no", "2", "shift", "move"]
OPTOUT_WORDS = ["stop", "unsubscribe", "optout"]

DATE_HINTS = ["today", "tomorrow", "tmrw", "tonight", "next week", "next",
              "monday", "tuesday", "wednesday", "thursday", "friday",
              "saturday", "sunday", "jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "sept", "oct", "nov", "dec"]


def _tokens(text):
    return set(text.replace(",", " ").replace(".", " ").replace("!", " ").split())


def _has(text, tokens, words):
    for w in words:
        if len(w) <= 3:
            if w in tokens:
                return True
        elif w in text:
            return True
    return False


def looks_like_date(text):
    t = (text or "").lower()
    if any(w in t for w in DATE_HINTS):
        return True
    return any(ch.isdigit() for ch in t)


def extract_date(text):
    """Return YYYY-MM-DD if the text contains a date, else None."""
    if not looks_like_date(text):
        return None
    try:
        default = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        dt = dateparser.parse(text, fuzzy=True, default=default)
    except (ValueError, OverflowError, TypeError):
        return None
    return dt.strftime("%Y-%m-%d")


def parse_reply(text):
    t = (text or "").strip().lower()
    tokens = _tokens(t)

    action = "unknown"
    if _has(t, tokens, OPTOUT_WORDS):
        action = "opt_out"
    elif _has(t, tokens, RESCHEDULE_WORDS):
        action = "reschedule"
    elif _has(t, tokens, CONFIRM_WORDS):
        action = "confirm"

    date = extract_date(text) if action == "reschedule" else None
    return {"action": action, "date": date}

# vigi/utils.py
import re

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def parse_emails(raw_text: str) -> list[str]:
    """
    Parse emails separated by newlines, commas, or semicolons.
    Returns unique, lowercased, valid emails (order preserved).
    """
    if not raw_text:
        return []

    parts = re.split(r"[,\n;]+", raw_text)
    seen = set()
    out = []

    for part in parts:
        email = (part or "").strip().lower()
        if not email:
            continue
        if not _EMAIL_RE.match(email):
            continue
        if email not in seen:
            seen.add(email)
            out.append(email)

    return out

"""Replace em dashes and en dashes with plain punctuation.

The lab website uses no em (U+2014) or en (U+2013) dashes. Ranges and
compounds become hyphens ("2024-2027", "Human-AI"); dashes used as
parenthetical punctuation become commas.
"""
import re

DASHES = "‒–—―"   # figure dash, en dash, em dash, horizontal bar
_D = f"[{DASHES}]"


def undash(text):
    if not text or not re.search(_D, text):
        return text
    s = text
    # Ranges and compounds: digit-digit, word-word with no surrounding spaces.
    s = re.sub(rf"(\d)\s*{_D}\s*(\d)", r"\1-\2", s)
    s = re.sub(rf"(?<=[A-Za-z0-9.)\]])–(?=[A-Za-z0-9(\[])", "-", s)
    # Parenthetical dashes (spaced, or unspaced em dash between words) -> comma.
    s = re.sub(rf"\s+{_D}\s+", ", ", s)
    s = re.sub(rf"(?<=\w)[—―](?=\w)", ", ", s)
    # Leading dash in a list-like line ("— text") or anything left -> hyphen.
    s = re.sub(_D, "-", s)
    # Tidy punctuation produced by the replacements.
    s = re.sub(r",\s*([,.;:!?])", r"\1", s)
    return s

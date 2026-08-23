"""
dates.py — Normalise toutes les dates détectées dans un texte vers un format
unique, en toutes lettres : "14 septembre 2008" (jour + mois en français +
année sur 4 chiffres).

Formats reconnus en entrée :
  - JJ/MM/AA ou JJ/MM/AAAA           (14/09/08, 14/09/2008)
  - JJ-MM-AA ou JJ-MM-AAAA           (14-09-2008)
  - AAAA-MM-JJ (ISO)                 (2008-09-14)
  - JJ mois AAAA en toutes lettres   (14 septembre 2008, 1er janvier 2020)

Pour changer le format cible, seule la fonction _format_date() est à modifier.
"""
import re

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}
MONTHS_PATTERN = "|".join(MONTHS.keys())

MONTHS_NUM_TO_NAME = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre",
    11: "novembre", 12: "décembre",
}


def _expand_year(yy: str) -> str:
    """Convertit une année à 2 chiffres en 4 chiffres.
    Hypothèse (données personnelles récentes) : 00-30 -> 20xx, 31-99 -> 19xx."""
    if len(yy) == 4:
        return yy
    n = int(yy)
    return f"20{yy}" if n <= 30 else f"19{yy}"


def _format_date(day: int, month: int, year: str) -> str:
    """Formate en 'JJ mois AAAA', avec '1er' pour le premier jour du mois
    (convention française : pas de zéro devant les autres jours)."""
    day_str = "1er" if day == 1 else str(day)
    month_name = MONTHS_NUM_TO_NAME.get(month, str(month))
    return f"{day_str} {month_name} {year}"


def normalize_dates(text: str) -> str:
    """Remplace toutes les dates détectées dans le texte par le format 'JJ mois AAAA'."""

    # JJ/MM/AA(AA) ou JJ-MM-AA(AA)
    def repl_numeric(m):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return _format_date(int(d), int(mo), _expand_year(y))

    text = re.sub(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b", repl_numeric, text)

    # AAAA-MM-JJ (ISO)
    def repl_iso(m):
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return _format_date(int(d), int(mo), y)

    text = re.sub(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", repl_iso, text)

    # JJ (ou "1er") mois AAAA déjà en toutes lettres : on uniformise juste la
    # casse et la forme du jour (au cas où quelqu'un écrit "14éme" etc.)
    def repl_text(m):
        d, month_name, y = m.group(1), m.group(2).lower(), m.group(3)
        mo = MONTHS[month_name]
        return _format_date(int(d), mo, y)

    text = re.sub(
        rf"\b(\d{{1,2}})(?:er)?\s+({MONTHS_PATTERN})\s+(\d{{4}})\b",
        repl_text, text, flags=re.IGNORECASE,
    )

    return text
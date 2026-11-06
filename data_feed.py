"""
Ροή δεδομένων (data feed) για το ιστορικό EuroJackpot.

Πηγές (με σειρά προτεραιότητας):
  1. dev-baris/lottery-archive (GitHub raw CSV, ενημερώνεται καθημερινά)
  2. eurojackpot.org proxy JSON (επίσημη σελίδα, ανά ημερομηνία)
  3. Τοπικό bundled CSV (data/eurojackpot_history.csv) — πάντα διαθέσιμο

Έλεγχοι εγκυρότητας: 5 μοναδικοί κύριοι 1-50, 2 μοναδικοί τζόκερ 1-12,
έγκυρη ημερομηνία, αφαίρεση διπλότυπων ημερομηνιών, ταξινόμηση αύξουσα.

ΣΗΜΕΙΩΣΗ για τις εποχές του παιχνιδιού (σημαντικό για τα στατιστικά):
  2012-03-23 → 2014-02-28 : τζόκερ από 1-8
  2014-03-01 → 2022-02-28 : τζόκερ από 1-10
  2022-03-01 → σήμερα      : τζόκερ από 1-12
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional

import requests

from quantum_lottery.logger_setup import get_logger
from quantum_lottery.settings import HISTORY_CSV

log = get_logger("DataFeed")

DEVBARIS_CSV = "https://raw.githubusercontent.com/dev-baris/lottery-archive/main/eu/eurojackpot/results.csv"
EJ_PROXY = "https://www.eurojackpot.org/proxy.php?d=euroJackpot/{yyyymmdd}"

MAINS_MAX = 50
JOKER_MAX_BY_DATE = [
    (date(2014, 3, 1), 8),   # έως 28/02/2014 → μέγιστο 8
    (date(2022, 3, 1), 10),  # έως 28/02/2022 → μέγιστο 10
    (date(9999, 12, 31), 12),  # από 01/03/2022 → μέγιστο 12
]


def joker_pool(d: date) -> int:
    """Επιστρέφει το μέγεθος της δεξαμενής τζόκερ για την ημερομηνία δήλωσης."""
    for since, pool in JOKER_MAX_BY_DATE:
        if d < since:
            return pool
    return 12


@dataclass(frozen=True)
class Draw:
    """Μία κλήρωση EuroJackpot."""
    d: date
    mains: tuple  # 5 αριθμοί 1-50, ταξινομημένοι
    jokers: tuple  # 2 αριθμοί 1-12, ταξινομημένοι

    @property
    def joker_max(self) -> int:
        return joker_pool(self.d)


def _parse_row(values: Iterable[str]) -> Optional[Draw]:
    """Μετατρέπει μια γραμμή CSV σε Draw ή επιστρέφει None αν είναι άκυρη."""
    try:
        v = [x.strip() for x in values]
        if len(v) < 7 or not v[0]:
            return None
        d = datetime.strptime(v[0], "%Y-%m-%d").date()
        mains = tuple(sorted(int(x) for x in v[1:6]))
        jokers = tuple(sorted(int(x) for x in v[6:8]))
        if len(set(mains)) != 5 or any(n < 1 or n > MAINS_MAX for n in mains):
            log.warning("Άκυροι κύριοι αριθμοί %s (%s) — παραλείπεται", mains, d)
            return None
        jmax = joker_pool(d)
        if len(set(jokers)) != 2 or any(n < 1 or n > jmax for n in jokers):
            log.warning("Άκυροι τζόκερ %s (%s, δεξαμενή 1-%d) — παραλείπεται", jokers, d, jmax)
            return None
        return Draw(d, mains, jokers)
    except (ValueError, TypeError):
        return None


def load_csv_text(text: str) -> List[Draw]:
    """Διαβάζει CSV (κόμμα ή ελληνικό ερωτηματικό) σε λίστα Draw."""
    draws: List[Draw] = []
    seen: set = set()
    delim = ";" if text.count(";") > text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    for row in reader:
        if not row or row[0].strip().lower() in ("date", "ημερομηνια"):
            continue
        dr = _parse_row(row)
        if dr and dr.d not in seen:
            seen.add(dr.d)
            draws.append(dr)
    draws.sort(key=lambda x: x.d)
    return draws


def load_local() -> List[Draw]:
    """Φορτώνει το τοπικό ιστορικό CSV."""
    if not HISTORY_CSV.exists():
        return []
    return load_csv_text(HISTORY_CSV.read_text(encoding="utf-8"))


def fetch_devbaris(timeout: int = 30) -> Optional[List[Draw]]:
    """Πηγή 1: πλήρες ιστορικό από το lottery-archive του dev-baris."""
    try:
        r = requests.get(DEVBARIS_CSV, timeout=timeout)
        r.raise_for_status()
        return load_csv_text(r.text)
    except requests.RequestException as exc:
        log.warning("dev-baris/lottery-archive απέτυχε: %s", exc)
        return None


def fetch_official(dd: date, timeout: int = 20) -> Optional[Draw]:
    """Πηγή 2: επίσημο eurojackpot.org για συγκεκριμένη ημερομηνία (JSON)."""
    try:
        r = requests.get(EJ_PROXY.format(yyyymmdd=dd.strftime("%Y%m%d")), timeout=timeout)
        r.raise_for_status()
        payload = r.json()
        items = payload.get("last") or []
        if not items:
            return None
        it = items[0]
        nums = it.get("numbers") or []
        euros = it.get("euroNumbers") or []
        if len(nums) == 5 and len(euros) == 2:
            return _parse_row([dd.isoformat()] + [str(n) for n in nums] + [str(e) for e in euros])
        return None
    except (requests.RequestException, ValueError) as exc:
        log.warning("eurojackpot.org proxy απέτυχε για %s: %s", dd, exc)
        return None


def update_history() -> List[Draw]:
    """
    Ενημερώνει το τοπικό CSV από τις πηγές και επιστρέφει το πλήρες ιστορικό.
    Κρατά πάντα το τοπικό ως βάση, συμπληρώνει ό,τι λείπει.
    """
    local = load_local()
    remote = fetch_devbaris()
    if not remote:
        log.info("Χρήση μόνο τοπικού ιστορικού (%d κληρώσεις).", len(local))
        return local

    by_date = {dr.d: dr for dr in local}
    added = 0
    for dr in remote:
        if dr.d not in by_date:
            by_date[dr.d] = dr
            added += 1
    merged = sorted(by_date.values(), key=lambda x: x.d)
    if added:
        save_csv(merged)
        log.info("Προστέθηκαν %d νέες κληρώσεις → σύνολο %d.", added, len(merged))
    else:
        log.info("Το ιστορικό είναι ενημερωμένο (%d κληρώσεις).", len(merged))
    return merged


def save_csv(draws: List[Draw]) -> None:
    """Αποθηκεύει το ιστορικό στο τοπικό CSV (format: date,n1..n5,e1,e2)."""
    lines = ["date,n1,n2,n3,n4,n5,e1,e2"]
    for dr in draws:
        lines.append(dr.d.isoformat() + "," + ",".join(str(n) for n in dr.mains + dr.jokers))
    HISTORY_CSV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def next_draw_date(last: date, today: Optional[date] = None) -> date:
    """Επόμενη ημερομηνία κλήρωσης: Τρίτη ή Παρασκευή, μετά την τελευταία."""
    from datetime import timedelta
    today = today or date.today()
    # αν σήμερα είναι Τρίτη(1)/Παρασκευή(4) και η τελευταία κλήρωση δεν είναι σήμερα
    for offset in range(0, 8):
        cand = today + timedelta(days=offset)
        if cand.weekday() in (1, 4) and cand > last:
            return cand
    return today

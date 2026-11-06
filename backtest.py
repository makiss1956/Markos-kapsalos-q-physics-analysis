"""
Walk-Forward Backtest — Ελεύθερη Αξιολόγηση σε Όλο το Ιστορικό
==============================================================

Για κάθε κλήρωση t (μετά την προθέρμανση):
  1. Χτίζουμε την κατάσταση ΜΟΝΟ από τις κληρώσεις < t (χωρίς διαρροή μέλλοντος)
  2. Παράγουμε πρόβλεψη Σκελετού Α (5+2), Σκελετού Β (3+1)
     και κλασικής πρόβλεψης
  3. Συγκρίνουμε με την πραγματική κλήρωση t (12 κατηγορίες βραβείων)

Έτσι προκύπτει αμερόληπτο μέτρο επίδοσης: πόσα βραβεία «έπιανε» το μοντέλο
σε όλο το ιστορικό, ανά κινητήρα και ανά σκελετό, σε σύγκριση με την
θεωρητική αναμενόμενη συχνότητα τυχαίων συμμετοχών.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from quantum_lottery.classic_engine import ClassicEngine
from quantum_lottery.comparison import PRIZE_TIERS, tier_of
from quantum_lottery.data_feed import Draw
from quantum_lottery.logger_setup import get_logger
from quantum_lottery.predictor import Predictor
from quantum_lottery.quantum_engine import QuantumEngine
from quantum_lottery.settings import REPORTS_DIR, SETTINGS

log = get_logger("Backtest")

CHECKPOINT_FILE = REPORTS_DIR / "backtest_checkpoint.json"


@dataclass
class BacktestResult:
    """Συγκεντρωτικό αποτέλεσμα backtest."""
    n_evaluated: int = 0
    n_warmup: int = 0
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    tiers: Dict[str, Dict[str, int]] = field(default_factory=dict)   # key → tier → πλήθος
    tickets: Dict[str, int] = field(default_factory=dict)            # key → συμμετοχές
    elapsed_sec: float = 0.0

    def add_hit(self, key: str, tier) -> None:
        self.tickets[key] = self.tickets.get(key, 0) + 1
        b = self.tiers.setdefault(key, {})
        b[tier or "none"] = b.get(tier or "none", 0) + 1

    def summary(self) -> str:
        lines = [
            f"Αξιολογήθηκαν {self.n_evaluated} κληρώσεις "
            f"({self.first_date:%d/%m/%Y} → {self.last_date:%d/%m/%Y}), "
            f"προθέρμανση {self.n_warmup}, χρόνος {self.elapsed_sec:.0f}s",
            "",
            f"{'Μοντέλο/Σκελετός':<22}{'Συμμετοχές':>11}{'Βραβεία':>9}  Κατανομή",
            "-" * 78,
        ]
        for key in sorted(self.tickets):
            t = self.tiers.get(key, {})
            won = sum(v for k, v in t.items() if k != "none")
            dist = ", ".join(f"{k}:{v}" for k, v in sorted(t.items(), key=lambda x: -x[1]) if k != "none")
            lines.append(f"{key:<22}{self.tickets[key]:>11}{won:>9}  {dist or '—'}")
        return "\n".join(lines)


def _save_checkpoint(next_t: int, res: "BacktestResult", fingerprint: dict) -> None:
    try:
        payload = {
            "fingerprint": fingerprint,
            "next_t": next_t,
            "res": {
                "n_evaluated": res.n_evaluated, "n_warmup": res.n_warmup,
                "first_date": res.first_date.isoformat() if res.first_date else None,
                "last_date": res.last_date.isoformat() if res.last_date else None,
                "tiers": res.tiers, "tickets": res.tickets,
                "elapsed_sec": res.elapsed_sec,
            },
        }
        CHECKPOINT_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("Δεν αποθηκεύτηκε το checkpoint: %s", exc)


def _load_checkpoint(fingerprint: dict):
    """Επιστρέφει (next_t, res) ή None αν δεν υπάρχει έγκυρο checkpoint."""
    if not CHECKPOINT_FILE.exists():
        return None
    try:
        payload = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        if payload.get("fingerprint") != fingerprint:
            log.info("Το checkpoint είναι από άλλη ρύθμιση — εκκίνηση από την αρχή.")
            return None
        r = payload["res"]
        res = BacktestResult(
            n_evaluated=r["n_evaluated"], n_warmup=r["n_warmup"],
            first_date=date.fromisoformat(r["first_date"]) if r["first_date"] else None,
            last_date=date.fromisoformat(r["last_date"]) if r["last_date"] else None,
            tiers={k: dict(v) for k, v in r["tiers"].items()},
            tickets=dict(r["tickets"]),
            elapsed_sec=r["elapsed_sec"],
        )
        log.info("Συνέχεια backtest από κλήρωση #%d (%d ήδη αξιολογημένες)",
                 payload["next_t"], res.n_evaluated)
        return payload["next_t"], res
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        log.warning("Άκυρο checkpoint (%s) — εκκίνηση από την αρχή.", exc)
        return None


def run_backtest(history: List[Draw], depth: int = 0,
                 progress_every: int = 25, resume: bool = True) -> BacktestResult:
    """
    Τρέχει walk-forward αξιολόγηση. depth=0 → όλο το ιστορικό μετά την
    προθέρμανση. Με resume=True συνεχίζει από checkpoint αν υπάρχει
    (χρήσιμο για διακοπτόμενες μεγάλες εκτελέσεις).
    """
    qe = QuantumEngine(SETTINGS.quantum)
    ce = ClassicEngine()
    predictor = Predictor(qe, ce)
    warmup = max(SETTINGS.warmup_draws, 60)
    start_idx = warmup
    end_idx = len(history) if depth in (0, -1) else min(len(history), len(history) - depth)
    end_idx = max(end_idx, start_idx + 1)

    fingerprint = {"n_history": len(history), "depth": depth, "warmup": warmup,
                   "w_int": SETTINGS.quantum.w_interference,
                   "w_ent": SETTINGS.quantum.w_entanglement,
                   "w_tun": SETTINGS.quantum.w_tunneling}

    res = BacktestResult(n_warmup=warmup)
    begin_t = start_idx
    if resume:
        ck = _load_checkpoint(fingerprint)
        if ck:
            begin_t, res = ck

    # σίγαση των verbose logs ανά βήμα κατά το backtest
    for name in ("Predictor", "QuantumEngine", "ClassicEngine", "HistoryStore"):
        logging.getLogger(name).setLevel(logging.WARNING)

    t0 = time.time()
    log.info("Backtest: κληρώσεις %d→%d (προθέρμανση %d)", begin_t, end_idx - 1, warmup)

    for t in range(begin_t, end_idx):
        dr = history[t]
        # 1) κατάσταση ΜΟΝΟ από το παρελθόν
        sub = history[:t]
        # 2) πρόβλεψη (ντετερμινιστική)
        try:
            pred = predictor.predict(sub, dr.d)
        except ValueError:
            continue
        # 3) σύγκριση με την πραγματική κλήρωση
        pm, pj = pred.skeleton_a, pred.jokers_a
        tier = tier_of(len(set(pm) & set(dr.mains)), len(set(pj) & set(dr.jokers)))
        res.add_hit("quantum-A", tier)
        pm, pj = pred.skeleton_b, (pred.joker_b,)
        tier = tier_of(len(set(pm) & set(dr.mains)), len(set(pj) & set(dr.jokers)))
        res.add_hit("quantum-B", tier)
        pm, pj = pred.classic_a, pred.classic_jokers
        tier = tier_of(len(set(pm) & set(dr.mains)), len(set(pj) & set(dr.jokers)))
        res.add_hit("classic-A", tier)
        pm, pj = pred.classic_b, (pred.classic_joker_b,)
        tier = tier_of(len(set(pm) & set(dr.mains)), len(set(pj) & set(dr.jokers)))
        res.add_hit("classic-B", tier)

        res.n_evaluated += 1
        if res.first_date is None:
            res.first_date = dr.d
        res.last_date = dr.d
        if progress_every and (res.n_evaluated % progress_every == 0):
            res.elapsed_sec += time.time() - t0
            t0 = time.time()
            log.info("  … %d/%d κληρώσεις", res.n_evaluated, end_idx - start_idx)
            _save_checkpoint(t + 1, res, fingerprint)

    res.elapsed_sec += time.time() - t0
    # καθάρισμα checkpoint μετά την επιτυχή ολοκλήρωση
    try:
        CHECKPOINT_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    # επαναφορά επιπέδων logs
    for name in ("Predictor", "QuantumEngine", "ClassicEngine", "HistoryStore"):
        logging.getLogger(name).setLevel(logging.INFO)
    log.info("Backtest ολοκληρώθηκε σε %.1f s", res.elapsed_sec)
    return res

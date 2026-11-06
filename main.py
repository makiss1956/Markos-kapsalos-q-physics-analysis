#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quantum Lottery Analysis V2 — Κεντρικό CLI (Main)
=================================================
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

__version__ = "2.0.0"

from quantum_lottery.backtest import run_backtest
from quantum_lottery.classic_engine import ClassicEngine
from quantum_lottery.comparison import compare_prediction
from quantum_lottery.data_feed import Draw, load_local, next_draw_date, update_history
from quantum_lottery.emailer import send_html
from quantum_lottery.history_store import (append_event, lifetime_stats,
                                           pending_predictions, read_events)
from quantum_lottery.logger_setup import get_logger, setup_logging
from quantum_lottery.predictor import Predictor
from quantum_lottery.quantum_engine import QuantumEngine, TOTAL_UNIVERSES
from quantum_lottery.reporting import build_html
from quantum_lottery.settings import PROJECT_ROOT, REPORTS_DIR, SETTINGS

log = get_logger("CLI")


def _engines() -> Tuple[QuantumEngine, ClassicEngine, Predictor]:
    qe = QuantumEngine(SETTINGS.quantum)
    ce = ClassicEngine()
    return qe, ce, Predictor(qe, ce)


def cmd_fetch(args) -> int:
    setup_logging()
    draws = update_history()
    print(f"✔ Ιστορικό: {len(draws)} κληρώσεις ({draws[0].d:%d/%m/%Y} → {draws[-1].d:%d/%m/%Y})")
    return 0


def _do_predictions(draws: List[Draw], send_by_email: bool = True) -> int:
    if len(draws) < SETTINGS.warmup_draws:
        log.error("Ανεπαρκές ιστορικό (%d κληρώσεις) — τρέξε πρώτα `fetch`.", len(draws))
        return 1
    target = next_draw_date(draws[-1].d)
    _, _, predictor = _engines()
    pred = predictor.predict(draws, target)

    comparisons = []
    last_date = draws[-1].d
    pend = [p for p in pending_predictions()
            if datetime.fromisoformat(p["target_date"]).date() <= last_date]
    if pend:
        latest = draws[-1]
        for p in pend:
            pa = tuple(p["skeleton_a"]); ja = tuple(p["jokers_a"])
            comparisons.append(compare_prediction(p.get("engine", "quantum"), "A", pa, ja, latest))
            pb = tuple(p["skeleton_b"]); jb = (int(p["joker_b"]),)
            comparisons.append(compare_prediction(p.get("engine", "quantum"), "B", pb, jb, latest))
            append_event({
                "type": "comparison", "target_date": p["target_date"],
                "actual_date": latest.d.isoformat(),
                "actual_mains": list(latest.mains), "actual_jokers": list(latest.jokers),
                "results": [c.to_dict() for c in comparisons[-2:]],
            })

    append_event({
        "type": "prediction", "target_date": target.isoformat(),
        "n_history": len(draws), **pred.to_dict(),
    })

    html = build_html(pred, comparisons or None, lifetime_stats(), target)
    stamp = target.isoformat()
    out_html = REPORTS_DIR / f"prediction_{stamp}.html"
    out_html.write_text(html, encoding="utf-8")
    subject = f"🔮 Quantum EuroJackpot — πρόβλεψη για {target.strftime('%d/%m/%Y')}"
    sent = send_html(subject, html) if send_by_email else False
    if send_by_email:
        append_event({"type": "email", "target_date": stamp, "sent": bool(sent),
                      "saved_html": out_html.name})

    print("=" * 64)
    print(f"  ΠΡΟΒΛΕΨΗ για την κλήρωση {target:%d/%m/%Y}")
    print(f"  Σκελετός Α (5+2):  {' '.join(f'{n:2d}' for n in pred.skeleton_a)}  ✦ {' '.join(f'{n:2d}' for n in pred.jokers_a)}")
    print(f"  Σκελετός Β (3+1):  {' '.join(f'{n:2d}' for n in pred.skeleton_b)}  ✦ {pred.joker_b:2d}")
    print(f"  Εστάλη email: {'ναι' if sent else 'όχι (αποθηκεύτηκε ' + out_html.name + ')'}")
    print("=" * 64)
    return 0


def cmd_predict(args) -> int:
    setup_logging()
    draws = load_local()
    if not draws:
        log.error("Δεν υπάρχει ιστορικό — τρέξε πρώτα `python3 main.py fetch`.")
        return 1
    return _do_predictions(draws, send_by_email=not args.no_email)


def cmd_auto(args) -> int:
    setup_logging()
    draws = update_history()
    if not draws:
        log.error("Κανένα ιστορικό διαθέσιμο — έλεγξε τη σύνδεση.")
        return 1
    return _do_predictions(draws, send_by_email=not args.no_email)


def cmd_test_email(args) -> int:
    setup_logging()
    html = "<body style='font-family:Arial;background:#0b1026;color:#e8ecf7;padding:30px'><h1>🔮 Quantum EuroJackpot</h1><p>Η σύνδεση email λειτουργεί σωστά!</p></body>"
    ok = send_html("🔮 Quantum EuroJackpot — δοκιμή σύνδεσης", html)
    print("✔ Το email εστάλη!" if ok else "✖ Δεν στάλθηκε — έλεγξε τα Secrets στο GitHub.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="main", description="Quantum Lottery Analysis V2")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fetch", help="ενημέρωση ιστορικού").set_defaults(fn=cmd_fetch)
    p = sub.add_parser("predict", help="νέα πρόβλεψη")
    p.add_argument("--no-email", action="store_true")
    p.set_defaults(fn=cmd_predict)
    sub.add_parser("auto", help="fetch→predict→email").set_defaults(fn=cmd_auto)
    sub.add_parser("test-email", help="δοκιμαστικό email").set_defaults(fn=cmd_test_email)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

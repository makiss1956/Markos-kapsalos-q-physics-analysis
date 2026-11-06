#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quantum Lottery Analysis V2 — Κεντρικό CLI
==========================================

Εντολές:
  fetch      Ενημέρωση του ιστορικού από τις πηγές δεδομένων
  predict    Νέα πρόβλεψη για την επόμενη κλήρωση (αποθήκευση + HTML)
  compare    Σύγκριση εκκρεμών προβλέψεων με την τελευταία κλήρωση
  auto       fetch → compare → predict → email  (για cron, Τρίτη & Παρασκευή)
  backtest   Walk-forward αξιολόγηση σε όλο το ιστορικό
  report     Συσσωρευμένα στατιστικά από το μόνιμο ιστορικό
  status     Σύντομη εικόνα κατάστασης
  test-email Δοκιμαστική αποστολή email

Παραδείγματα:
  python3 quantum_lottery.py auto
  python3 quantum_lottery.py predict --no-email
  python3 quantum_lottery.py backtest --depth 0
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Tuple

# ώστε το script να τρέχει και ως `python3 quantum_lottery.py` από οποιονδήποτε φάκελο
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantum_lottery import __version__
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
    """Ενημέρωση ιστορικού."""
    setup_logging()
    draws = update_history()
    print(f"✔ Ιστορικό: {len(draws)} κληρώσεις "
          f"({draws[0].d:%d/%m/%Y} → {draws[-1].d:%d/%m/%Y})")
    return 0


def _do_predictions(draws: List[Draw], send_by_email: bool = True) -> int:
    """Δημιουργεί την πρόβλεψη, την καταχωρεί, χτίζει HTML και (προαιρετικά) στέλνει."""
    if len(draws) < SETTINGS.warmup_draws:
        log.error("Ανεπαρκές ιστορικό (%d κληρώσεις) — τρέξε πρώτα `fetch`.", len(draws))
        return 1
    target = next_draw_date(draws[-1].d)
    _, _, predictor = _engines()
    pred = predictor.predict(draws, target)

    # σύγκριση εκκρεμών προβλέψεων ΜΟΝΟ όταν η κλήρωση-στόχος έχει πραγματοποιηθεί
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
    # η αναφορά πάντα αποθηκεύεται τοπικά (ανεξαρτήτως email)
    out_html.write_text(html, encoding="utf-8")
    subject = f"🔮 Quantum EuroJackpot — πρόβλεψη για {target.strftime('%d/%m/%Y')}"
    sent = send_html(subject, html) if send_by_email else False
    if send_by_email:
        append_event({"type": "email", "target_date": stamp, "sent": bool(sent),
                      "saved_html": out_html.name})

    print("=" * 64)
    print(f"  ΠΡΟΒΛΕΨΗ για την κλήρωση {target:%d/%m/%Y}")
    print(f"  Σκελετός Α (5+2):  {' '.join(f'{n:2d}' for n in pred.skeleton_a)}"
          f"  ✦ {' '.join(f'{n:2d}' for n in pred.jokers_a)}")
    for a in pred.alternatives:
        print(f"  Εναλλακτικό #{a['rank']}: {' '.join(f'{n:2d}' for n in a['mains'])}"
              f"  ✦ {' '.join(f'{n:2d}' for n in a['jokers'])}")
    print(f"  Σκελετός Β (3+1):  {' '.join(f'{n:2d}' for n in pred.skeleton_b)}"
          f"  ✦ {pred.joker_b:2d}")
    print(f"  Κλασικό (5+2):     {' '.join(f'{n:2d}' for n in pred.classic_a)}"
          f"  ✦ {' '.join(f'{n:2d}' for n in pred.classic_jokers)}")
    print(f"  Εστάλη email: {'ναι' if sent else 'όχι (αποθηκεύτηκε ' + out_html.name + ')'}")
    print("=" * 64)
    return 0


def cmd_predict(args) -> int:
    """Νέα πρόβλεψη χωρίς ενημέρωση πηγών."""
    setup_logging()
    draws = load_local()
    if not draws:
        log.error("Δεν υπάρχει ιστορικό — τρέξε πρώτα `python3 quantum_lottery.py fetch`.")
        return 1
    return _do_predictions(draws, send_by_email=not args.no_email)


def cmd_compare(args) -> int:
    """Σύγκριση εκκρεμών προβλέψεων με την τελευταία κλήρωση."""
    setup_logging()
    draws = load_local()
    pend = pending_predictions()
    if not pend:
        print("Δεν υπάρχουν εκκρεμείς προβλέψεις για σύγκριση.")
        return 0
    return _do_predictions(draws, send_by_email=not args.no_email)


def cmd_auto(args) -> int:
    """Πλήρες κύκλωμα για cron: fetch → compare → predict → email."""
    setup_logging()
    draws = update_history()
    if not draws:
        log.error("Κανένα ιστορικό διαθέσιμο — έλεγξε τη σύνδεση.")
        return 1
    return _do_predictions(draws, send_by_email=not args.no_email)


def cmd_backtest(args) -> int:
    """Walk-forward αξιολόγηση σε όλο το ιστορικό."""
    setup_logging()
    draws = load_local()
    if len(draws) < SETTINGS.warmup_draws + 10:
        log.error("Ανεπαρκές ιστορικό για backtest.")
        return 1
    depth = args.depth if args.depth else SETTINGS.backtest_depth
    res = run_backtest(draws, depth=depth)
    summary = res.summary()
    print(summary)
    out = REPORTS_DIR / f"backtest_{date.today().isoformat()}.md"
    out.write_text(f"# Backtest Quantum Lottery v2 — {date.today().isoformat()}\n\n"
                   f"```\n{summary}\n```\n", encoding="utf-8")
    log.info("Το αποτέλεσμα αποθηκεύτηκε: %s", out.name)
    return 0


def cmd_report(args) -> int:
    """Συσσωρευμένα στατιστικά."""
    setup_logging(console=False)
    st = lifetime_stats()
    ev = read_events()
    preds = [e for e in ev if e.get("type") == "prediction"]
    comps = [e for e in ev if e.get("type") == "comparison"]
    mails = [e for e in ev if e.get("type") == "email"]
    print("── Στατιστικά συστήματος ──────────────────────────")
    print(f"  Προβλέψεις: {len(preds)} | Συγκρίσεις: {len(comps)} | Emails: {len(mails)}")
    if not st.get("tickets"):
        print("  (δεν έχουν καταγραφεί ακόμα συγκρίσεις)")
    for key, cnt in sorted(st["tickets"].items()):
        tiers = st["tiers"].get(key, {})
        won = sum(v for k, v in tiers.items() if k != "none")
        print(f"  {key}: {cnt} συμμετοχές, {won} βραβεία")
    return 0


def cmd_status(args) -> int:
    """Σύντομη εικόνα κατάστασης."""
    setup_logging(console=False)
    draws = load_local()
    if not draws:
        print("⚠ Κανένα ιστορικό. Τρέξε: python3 quantum_lottery.py fetch")
        return 1
    nxt = next_draw_date(draws[-1].d)
    print(f"✔ Ιστορικό: {len(draws)} κληρώσεις (τελευταία {draws[-1].d:%d/%m/%Y})")
    print(f"✔ Επόμενη κλήρωση: {nxt:%d/%m/%Y} ({'Τρίτη' if nxt.weekday() == 1 else 'Παρασκευή'})")
    print(f"✔ Εκκρεμείς προβλέψεις: {len(pending_predictions())}")
    print(f"✔ Universe space: {TOTAL_UNIVERSES:,} κλαδιά")
    return 0


def cmd_test_email(args) -> int:
    """Δοκιμαστικό email."""
    setup_logging()
    html = ("<body style='font-family:Arial;background:#0b1026;color:#e8ecf7;padding:30px'>"
            "<h1>🔮 Quantum EuroJackpot</h1><p>Η σύνδεση email λειτουργεί σωστά!</p></body>")
    ok = send_html("🔮 Quantum EuroJackpot — δοκιμή σύνδεσης", html)
    print("✔ Το email εστάλη!" if ok else "✖ Δεν στάλθηκε — έλεγξε το .env (δες INSTALL_GUIDE_LINUX.md)")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="quantum_lottery",
        description="Quantum Lottery Analysis V2 — κβαντική ανάλυση EuroJackpot")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fetch", help="ενημέρωση ιστορικού από τις πηγές").set_defaults(fn=cmd_fetch)
    p = sub.add_parser("predict", help="νέα πρόβλεψη για επόμενη κλήρωση")
    p.add_argument("--no-email", action="store_true", help="χωρίς αποστολή email")
    p.set_defaults(fn=cmd_predict)
    p = sub.add_parser("compare", help="σύγκριση εκκρεμών προβλέψεων")
    p.add_argument("--no-email", action="store_true")
    p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("auto", help="fetch→compare→predict→email (για cron)")
    p.add_argument("--no-email", action="store_true")
    p.set_defaults(fn=cmd_auto)
    p = sub.add_parser("backtest", help="walk-forward αξιολόγηση ιστορικού")
    p.add_argument("--depth", type=int, default=0, help="πόσες κληρώσεις (0=όλες)")
    p.set_defaults(fn=cmd_backtest)
    sub.add_parser("report", help="συσσωρευμένα στατιστικά").set_defaults(fn=cmd_report)
    sub.add_parser("status", help="σύντομη εικόνα κατάστασης").set_defaults(fn=cmd_status)
    sub.add_parser("test-email", help="δοκιμαστικό email").set_defaults(fn=cmd_test_email)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

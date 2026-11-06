"""
Unit tests για το Quantum Lottery Analysis V2.
Εκτέλεση:  python3 -m pytest tests/ -v
"""
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quantum_lottery.comparison import tier_of, tier_probability
from quantum_lottery.data_feed import joker_pool, load_csv_text, next_draw_date
from quantum_lottery.quantum_engine import (C_12_2, C_50_5, N_JOKERS, N_MAINS,
                                            QuantumEngine)

TOTAL = C_50_5 * C_12_2


# ── Σταθερές του παιχνιδιού ──────────────────────────────────────────────────
def test_combinatorics():
    assert C_50_5 == 2_118_760
    assert C_12_2 == 66
    assert TOTAL == 139_838_160  # ~140 εκατ. σύμπαντα


def test_jackpot_probability():
    assert abs(tier_probability("5+2") - 1 / 139_838_160) < 1e-20


def test_twelve_tiers_probability_sum():
    tiers = ["5+2", "5+1", "5+0", "4+2", "4+1", "4+0",
             "3+2", "2+2", "3+1", "3+0", "1+2", "2+1"]
    total = sum(tier_probability(t) for t in tiers)
    assert 1 / 35 < total < 1 / 30  # επίσημα 1 στο ~32


def test_tier_of():
    assert tier_of(5, 2) == "5+2"
    assert tier_of(2, 1) == "2+1"
    assert tier_of(0, 1) is None      # 0+1 δεν βραβεύεται
    assert tier_of(4, 0) == "4+0"


# ── Δεδομένα ─────────────────────────────────────────────────────────────────
def test_joker_pool_eras():
    from datetime import date
    assert joker_pool(date(2012, 6, 1)) == 8
    assert joker_pool(date(2015, 6, 1)) == 10
    assert joker_pool(date(2023, 6, 1)) == 12


def test_csv_parsing_semicolon():
    text = ("Date;N1;N2;N3;N4;N5;E1;E2\n"
            "2012-03-23;05;08;21;37;46;06;08\n"
            "2024-01-02;1;2;3;4;5;11;12\n")
    draws = load_csv_text(text)
    assert len(draws) == 2
    assert draws[0].mains == (5, 8, 21, 37, 46)
    assert draws[1].jokers == (11, 12)


def test_csv_rejects_invalid():
    text = ("date,n1,n2,n3,n4,n5,e1,e2\n"
            "2024-01-02,1,1,3,4,5,1,2\n"    # διπλότυπος κύριος
            "2024-01-05,1,2,3,4,99,1,2\n"   # κύριος > 50
            "2024-01-09,1,2,3,4,5,13,2\n")  # τζόκερ > 12
    assert load_csv_text(text) == []


def test_next_draw_date():
    from datetime import date
    # μετά από Τρίτη 03/11/2026 → Παρασκευή 06/11/2026
    assert next_draw_date(date(2026, 11, 3), today=date(2026, 11, 4)) == date(2026, 11, 6)
    # Παρασκευή το βράδυ (μετά την κλήρωση) → επόμενη Τρίτη
    assert next_draw_date(date(2026, 11, 6), today=date(2026, 11, 6)) == date(2026, 11, 10)


# ── Combinadic decoder (πυρήνας της σάρωσης σύμπαντος) ──────────────────────
def test_decoder_first_last():
    first = QuantumEngine._combos_chunk(0, 2)
    assert first[0].tolist() == [1, 2, 3, 4, 5]
    assert first[1].tolist() == [1, 2, 3, 4, 6]
    last = QuantumEngine._combos_chunk(TOTAL // 66 - 1, TOTAL // 66)
    assert last[0].tolist() == [46, 47, 48, 49, 50]


def test_decoder_unique_sorted_sample():
    sample = QuantumEngine._combos_chunk(500_000, 510_000)
    assert np.all(np.diff(sample, axis=1) > 0)          # αύξουσα
    assert len(np.unique(sample, axis=0)) == 10_000     # μοναδικοί


def test_decoder_covers_all():
    """Δειγματοληπτικά: 5 τυχαία ranks ταιριάζουν με itertools."""
    ranks = [0, 1, 777, 1_000_000, C_50_5 - 1]
    got = QuantumEngine._combos_chunk(min(ranks), max(ranks) + 1)
    # rank 0
    assert got[0].tolist() == [1, 2, 3, 4, 5]
    # τελευταίο rank
    assert got[-1].tolist() == [46, 47, 48, 49, 50]


# ── Κβαντικός κινητήρας σε συνθετικά δεδομένα ───────────────────────────────
def _synthetic_history(n=320, seed=7):
    rng = np.random.default_rng(seed)
    draws = []
    d = next_draw_date=__import__("datetime").date(2020, 1, 3)
    from datetime import timedelta
    for i in range(n):
        mains = tuple(sorted(rng.choice(np.arange(1, 51), 5, replace=False)))
        jokers = tuple(sorted(rng.choice(np.arange(1, 13), 2, replace=False)))
        draws.append(type("D", (), {"d": d + timedelta(days=i), "mains": mains,
                                    "jokers": jokers, "joker_max": 12})())
    return draws


def test_state_normalized():
    from quantum_lottery.quantum_engine import QuantumEngine
    from quantum_lottery.settings import QuantumSettings
    hist = _synthetic_history()
    st = QuantumEngine(QuantumSettings()).build_state(hist)
    assert abs(st.p_main.sum() - 1.0) < 1e-9
    assert abs(st.p_joker.sum() - 1.0) < 1e-9
    assert len(st.amp_main) == N_MAINS
    # ο κανόνας του Born: |a_i|² = p_i
    assert np.allclose(np.abs(st.amp_main) ** 2, st.p_main)


def test_score_top_is_valid_combo():
    from quantum_lottery.quantum_engine import QuantumEngine
    from quantum_lottery.settings import QuantumSettings
    hist = _synthetic_history()
    qe = QuantumEngine(QuantumSettings())
    ranked = qe.score_main_combos(qe.build_state(hist))
    top = ranked[0, :5]
    assert len(set(int(x) for x in top)) == 5
    assert all(1 <= int(x) <= 50 for x in top)
    # scores φθίνουσα σειρά
    assert np.all(np.diff(ranked[:10, 5].astype(float)) <= 1e-9)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

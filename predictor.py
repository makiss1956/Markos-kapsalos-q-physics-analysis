"""
Παραγωγός Προβλέψεων (Predictor)
================================

Συνδυάζει τον κβαντικό κινητήρα και τον κλασικό και παράγει:

  • Σκελετός Α  : 5 κύριοι + 2 τζόκερ   (το «σύμπαν» μέγιστης βαρύτητας)
  • Εναλλακτικά : 2 ακόμα σύνολα 5+2    (2ο και 3ο «κλαδί σύμπαντος»,
                    με ελάχιστη απόσταση 2 αριθμών από τον Σκελετό Α)
  • Σκελετός Β  : 3 κύριοι + 1 τζόκερ   (κατάρρευση μερικής παρατήρησης)
  • Top-10      : πίνακας πυκνοτήτων πιθανότητας κύριων/τζόκερ
  • Κλασική     : 5+2 και 3+1 από τον κλασικό κινητήρα (σύγκριση)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Tuple

import numpy as np

from quantum_lottery.classic_engine import ClassicEngine
from quantum_lottery.data_feed import Draw
from quantum_lottery.logger_setup import get_logger
from quantum_lottery.quantum_engine import QuantumEngine, QuantumState
from quantum_lottery.settings import SETTINGS

log = get_logger("Predictor")


@dataclass
class Prediction:
    """Μία πλήρης πρόβλεψη για συγκεκριμένη κλήρωση."""
    target_date: date
    skeleton_a: Tuple[int, ...]          # 5 κύριοι
    jokers_a: Tuple[int, ...]            # 2 τζόκερ
    skeleton_b: Tuple[int, ...]          # 3 κύριοι
    joker_b: int                         # 1 τζόκερ
    alternatives: List[Dict] = field(default_factory=list)   # εναλλακτικά 5+2
    top_mains: List[Tuple[int, float]] = field(default_factory=list)  # top-10
    top_jokers: List[Tuple[int, float]] = field(default_factory=list)  # top-4
    entanglement_info: Dict[int, List[int]] = field(default_factory=dict)
    classic_a: Tuple[int, ...] = ()
    classic_jokers: Tuple[int, ...] = ()
    classic_b: Tuple[int, ...] = ()
    classic_joker_b: int = 0
    branch_scores: Dict[str, float] = field(default_factory=dict)
    universes_scanned: int = 139_838_160

    def to_dict(self) -> Dict:
        return {
            "target_date": self.target_date.isoformat(),
            "skeleton_a": list(self.skeleton_a),
            "jokers_a": list(self.jokers_a),
            "skeleton_b": list(self.skeleton_b),
            "joker_b": self.joker_b,
            "alternatives": self.alternatives,
            "top_mains": [[n, round(p, 6)] for n, p in self.top_mains],
            "top_jokers": [[n, round(p, 6)] for n, p in self.top_jokers],
            "entanglement_info": {str(k): v for k, v in self.entanglement_info.items()},
            "classic_a": list(self.classic_a),
            "classic_jokers": list(self.classic_jokers),
            "classic_b": list(self.classic_b),
            "classic_joker_b": self.classic_joker_b,
            "branch_scores": self.branch_scores,
            "universes_scanned": self.universes_scanned,
        }


class Predictor:
    """Παράγει την πλήρη πρόβλεψη για την επόμενη κλήρωση."""

    def __init__(self, qe: QuantumEngine, ce: ClassicEngine):
        self.qe = qe
        self.ce = ce

    def predict(self, history: List[Draw], target: date) -> Prediction:
        """Κύρια είσοδος: ιστορικό + ημερομηνία-στόχος → πλήρης πρόβλεψη."""
        st = self.qe.build_state(history)

        # ── Σκελετός Α: το κλαδί σύμπαντος μέγιστης βαρύτητας ────────────────
        ranked_mains = self.qe.score_main_combos(st)      # (2.118.760, 6)
        joker_rows = self.qe.score_joker_pairs(st)        # 66 ζευγάρια
        best_mains = tuple(int(x) for x in ranked_mains[0, :5])
        best_jokers = tuple(int(x) for x in joker_rows[0][0])
        best_score = float(ranked_mains[0, 5])

        # ── Εναλλακτικά κλαδιά (2ο, 3ο σύμπαν) ───────────────────────────────
        alts: List[Dict] = []
        min_dist = SETTINGS.quantum.min_branch_distance
        used = [set(best_mains)]
        for row in ranked_mains[1:, :]:
            cand = tuple(int(x) for x in row[:5])
            if all(len(set(cand) ^ u) >= 2 * min_dist for u in used):
                used.append(set(cand))
                # κάθε εναλλακτικό κλαδί παίρνει και διαφορετικό ζεύγος τζόκερ
                jr = joker_rows[(len(alts) + 1) % len(joker_rows)][0]
                alts.append({
                    "mains": list(cand),
                    "jokers": list(jr),
                    "score": float(row[5]),
                    "rank": len(alts) + 1,
                })
            if len(alts) >= SETTINGS.quantum.alt_tickets:
                break

        # ── Σκελετός Β: κατάρρευση σε 3 κύριους + 1 τζόκερ ───────────────────
        ranked_triples = self.qe.score_main_triples(st)
        b_mains = tuple(int(x) for x in ranked_triples[0, :3])
        # τζόκερ Β: η μεγαλύτερη μεμονωμένη πυκνότητα τζόκερ
        b_joker = int(np.argmax(st.p_joker)) + 1
        b_score = float(ranked_triples[0, 3])

        # ── Πίνακες πυκνοτήτων ───────────────────────────────────────────────
        top_mains = self.qe.top_numbers(st, 10)
        top_jokers = self.qe.top_jokers(st, 4)
        ent_info = {n: self.qe.entanglement_partners(st, n, 3)
                    for n, _ in top_mains[:3]}

        # ── Κλασική πρόβλεψη (γύψο σύγκρισης) ────────────────────────────────
        cs = self.ce.analyze(history)
        c_mains = tuple(self.ce.best_mains(cs, 5))
        c_jokers = tuple(self.ce.best_jokers(cs, 2))
        c_b = tuple(self.ce.best_mains(cs, 3))
        c_bj = self.ce.best_jokers(cs, 1)[0]

        log.info("Πρόβλεψη για %s | Σκελετός Α: %s +%s | Σκελετός Β: %s +%d",
                 target, best_mains, best_jokers, b_mains, b_joker)

        return Prediction(
            target_date=target,
            skeleton_a=best_mains,
            jokers_a=best_jokers,
            skeleton_b=b_mains,
            joker_b=b_joker,
            alternatives=alts,
            top_mains=top_mains,
            top_jokers=top_jokers,
            entanglement_info=ent_info,
            classic_a=c_mains,
            classic_jokers=c_jokers,
            classic_b=c_b,
            classic_joker_b=c_bj,
            branch_scores={
                "skeleton_a": best_score,
                "skeleton_b": b_score,
                "best_joker_pair": float(joker_rows[0][1]),
            },
        )

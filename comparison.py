"""
Σύγκριση Προβλέψεων (Comparison)
================================

Αξιολογεί μια πρόβλεψη απέναντι σε πραγματική κλήρωση, σύμφωνα με τις 12
επίσημες κατηγορίες βραβείων του EuroJackpot, και υπολογίζει τις πιθανότητες
τύχης ανά κατηγορία (για ένα απλό δελτίο) ώστε να φαίνεται πόσο «τυχερή»
ήταν η πρόβλεψη σε σχέση με το τυχαίο.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from quantum_lottery.data_feed import Draw

# Οι 12 κατηγορίες βραβείων EuroJackpot (κύριοι + τζόκερ)
PRIZE_TIERS: Dict[str, str] = {
    "5+2": "1η — Jackpot",
    "5+1": "2η",
    "5+0": "3η",
    "4+2": "4η",
    "4+1": "5η",
    "4+0": "6η",
    "3+2": "7η",
    "2+2": "8η",
    "3+1": "9η",
    "3+0": "10η",
    "1+2": "11η",
    "2+1": "12η",
}


def tier_of(mains_hit: int, jokers_hit: int) -> Optional[str]:
    """Επιστρέφει την κατηγορία βραβείου ή None αν δεν υπάρχει βραβείο."""
    key = f"{mains_hit}+{jokers_hit}"
    return key if key in PRIZE_TIERS else None


def tier_probability(tier: str) -> float:
    """
    Πιθανότητα να κερδίσει ΜΙΑ απλή συμμετοχή τη συγκεκριμένη κατηγορία.
    Π = C(5,k)·C(45,5−k)/C(50,5) × C(2,j)·C(10,2−j)/C(12,2)
    """
    k, j = (int(x) for x in tier.split("+"))
    p_main = math.comb(5, k) * math.comb(45, 5 - k) / math.comb(50, 5)
    p_joker = math.comb(2, j) * math.comb(10, 2 - j) / math.comb(12, 2)
    return p_main * p_joker


def hits(pred_mains: Tuple[int, ...], pred_jokers: Tuple[int, ...],
         draw: Draw) -> Tuple[int, int, Optional[str]]:
    """Μετρά τις επιτυχίες μιας πρόβλεψης απέναντι στην κλήρωση."""
    mh = len(set(pred_mains) & set(draw.mains))
    jh = len(set(pred_jokers) & set(draw.jokers))
    return mh, jh, tier_of(mh, jh)


@dataclass
class ComparisonResult:
    """Αποτέλεσμα σύγκρισης μιας πρόβλεψης."""
    engine: str            # "quantum" | "classic"
    skeleton: str          # "A" | "B"
    predicted_mains: Tuple[int, ...]
    predicted_jokers: Tuple[int, ...]
    mains_hit: int
    jokers_hit: int
    tier: Optional[str]
    tier_label: str
    one_in: float          # «1 στις Χ» πιθανότητα της κατηγορίας

    def to_dict(self) -> Dict:
        return {
            "engine": self.engine,
            "skeleton": self.skeleton,
            "predicted_mains": list(self.predicted_mains),
            "predicted_jokers": list(self.predicted_jokers),
            "mains_hit": self.mains_hit,
            "jokers_hit": self.jokers_hit,
            "tier": self.tier,
            "one_in": self.one_in,
        }


def compare_prediction(engine: str, skeleton: str,
                       pred_mains: Tuple[int, ...], pred_jokers: Tuple[int, ...],
                       draw: Draw) -> ComparisonResult:
    """Σύγκρινε ένα ζεύγος (κύριοι, τζόκερ) με την κλήρωση."""
    mh, jh, tier = hits(pred_mains, pred_jokers, draw)
    if tier:
        p = tier_probability(tier)
        one_in = 1.0 / p if p > 0 else float("inf")
        label = PRIZE_TIERS[tier]
    else:
        one_in = float("inf")
        label = "χωρίς βραβείο"
    return ComparisonResult(engine, skeleton, tuple(pred_mains), tuple(pred_jokers),
                            mh, jh, tier, label, one_in)

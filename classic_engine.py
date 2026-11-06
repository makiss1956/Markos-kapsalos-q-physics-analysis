"""
Κλασικός Κινητήρας Στατιστικής (Classic Engine)
================================================

Παραδοσιακή προσέγγιση για σύγκριση με τον κβαντικό κινητήρα:
  • Συχνότητες με αποσύνθεση χρόνου (ποιοι αριθμοί «καίνε» πρόσφατα)
  • Καθυστέρηση/υπερβολή (πόσες κληρώσεις λείπει ένας αριθμός έναντι
    της αναμενόμενης εμφάνισης)
  • Συ-εμφανίσεις ζευγών (ποια ζεύγη βγαίνουν μαζί)

Σκορ αριθμού = w_freq·freq + w_delay·delay + w_pair·pair_heat
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import List, Sequence, Tuple

import numpy as np

from quantum_lottery.data_feed import Draw
from quantum_lottery.logger_setup import get_logger

log = get_logger("ClassicEngine")

N_MAINS = 50
N_JOKERS = 12


@dataclass
class ClassicScores:
    freq_main: np.ndarray
    delay_main: np.ndarray
    pair_main: np.ndarray      # θερμότητα ζεύγους ανά αριθμό (άθροισμα ανάγραμμα)
    freq_joker: np.ndarray
    delay_joker: np.ndarray


class ClassicEngine:
    """Κλασική στατιστική ανάλυση συχνοτήτων/καθυστερήσεων."""

    def __init__(self, w_freq: float = 0.7, w_delay: float = 0.3,
                 decay: float = 0.002, window: int = 600):
        self.w_freq = w_freq
        self.w_delay = w_delay
        self.decay = decay
        self.window = window

    def analyze(self, history: Sequence[Draw]) -> ClassicScores:
        """Υπολογίζει όλες τις κλασικές βαθμολογίες από το ιστορικό."""
        n = len(history)
        recent = history[-self.window:] if self.window and self.window < n else history
        m = len(recent)

        freq_main = np.zeros(N_MAINS)
        freq_joker = np.zeros(N_JOKERS)
        last_seen = np.full(N_MAINS, -1)
        last_seen_j = np.full(N_JOKERS, -1)

        for idx, dr in enumerate(recent):
            w = math.exp(-self.decay * (m - 1 - idx))
            mi = np.array(dr.mains) - 1
            jo = np.array(dr.jokers) - 1
            freq_main[mi] += w
            freq_joker[jo] += w
            for x in mi:
                last_seen[x] = idx
            for x in jo:
                last_seen_j[x] = idx

        freq_main /= freq_main.sum() or 1.0
        freq_joker /= freq_joker.sum() or 1.0

        # καθυστέρηση: πόσες κληρώσεις λείπει / αναμενόμενο διάστημα (50/5 = 10)
        gaps = np.where(last_seen >= 0, m - 1 - last_seen, m)
        delay_main = gaps / 10.0
        gaps_j = np.where(last_seen_j >= 0, m - 1 - last_seen_j, m)
        delay_joker = gaps_j / 6.0

        # θερμότητα ζευγών (αποσυντιθέμενη)
        pair_main = np.zeros((N_MAINS, N_MAINS))
        for idx, dr in enumerate(recent[-300:]):
            w = math.exp(-self.decay * (min(300, m) - 1 - idx))
            mi = np.array(dr.mains) - 1
            pair_main[np.ix_(mi, mi)] += w
        np.fill_diagonal(pair_main, 0.0)
        pair_heat = pair_main.sum(axis=1)
        pair_heat = pair_heat / (pair_heat.max() or 1.0)

        return ClassicScores(freq_main, delay_main, pair_heat, freq_joker, delay_joker)

    def best_mains(self, sc: ClassicScores, k: int = 5) -> List[int]:
        total = self.w_freq * sc.freq_main + self.w_delay * np.tanh(sc.delay_main) \
            + 0.15 * sc.pair_main
        idx = np.argsort(-total)[:k]
        return sorted(int(i) + 1 for i in idx)

    def best_jokers(self, sc: ClassicScores, k: int = 2) -> List[int]:
        total = self.w_freq * sc.freq_joker + self.w_delay * np.tanh(sc.delay_joker)
        idx = np.argsort(-total)[:k]
        return sorted(int(i) + 1 for i in idx)

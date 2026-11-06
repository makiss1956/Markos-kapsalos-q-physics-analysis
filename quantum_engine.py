"""
Κβαντικός Κινητήρας EuroJackpot (Quantum Engine)
================================================

Ο φυσικός πυρήνας του έργου. Κάθε κλήρωση μοντελοποιείται ως Κβαντικό
Σύστημα με τους εξής αντιστοιχισμούς (όλοι υλοποιημένοι σε NumPy):

  1. ΧΩΡΟΣ HILBERT   : 50 ορθοκανονικές βάσεις |1⟩…|50⟩ για τους κύριους
                       και 12 βάσεις |1⟩…|12⟩ για τους τζόκερ.
  2. ΠΛΑΣΗ (Born)    : |a_i|² = p_i, πυκνότητα εμφάνισης με αποσύνθεση
                       χρόνου (exponential decay) — «η κατάσταση ελαφρύνει»
                       όσο απομακρυνόμαστε χρονικά από μια παρατήρηση.
  3. ΚΥΜΑ-ΣΩΜΑΤΙΔΙΟ  : κάθε αριθμός έχει σωματιδιακή όψη (συχνότητα p_i)
                       και κυματική όψη (φάση φ_i από τον κύκλο επανεμφάνισης
                       — ο «παλμός» του αριθμού).
  4. ΑΛΛΗΛΕΠΙΔΡΑΣΗ   : διπλή σχισμή — όταν δύο αριθμοί «περνούν ταυτόχρονα»,
                       οι πλάσεις τους προστίθενται: ο σταυρός όρος
                       2√(p_i p_j)·cos(φ_i−φ_j) ενισχύει ή εξασθενεί ζεύγη.
  5. ΔΙΕΜΠΛΟΚΗ       : μήτρα E[i,j] από z-scores συ-εμφανίσεων ζευγών
                       έναντι της ανεξάρτητης προσδοκίας.
  6. ΚΒΑΝΤΙΚΗ ΔΙΟΔΕΥΣΗ: αριθμοί με απουσία > 2.5 κύκλους αποκτούν σμικρή
                       ώθηση — «διαπερνούν το φράγμα» της απουσίας.
  7. ΠΟΛΛΑΠΛΑ ΣΥΜΠΑΝΤΑ: βαδίζουμε ΟΛΑ τα 139.838.160 κλαδιά (C(50,5)·C(12,2))
                       και επιλέγουμε το κλαδί μέγιστης βαρύτητας για το
                       ΔΙΚΟ ΜΑΣ σύμπαν.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import List, Sequence, Tuple

import numpy as np

from quantum_lottery.data_feed import Draw
from quantum_lottery.logger_setup import get_logger
from quantum_lottery.settings import QuantumSettings

log = get_logger("QuantumEngine")

N_MAINS = 50
N_JOKERS = 12
C_50_5 = math.comb(50, 5)          # 2.118.760
C_12_2 = math.comb(12, 2)          # 66
TOTAL_UNIVERSES = C_50_5 * C_12_2  # 139.838.160

_PAIRS_5 = np.array(list(combinations(range(5), 2)))  # 10 ζεύγη θέσεων μέσα σε combo


@dataclass
class QuantumState:
    """Η κατάσταση του συστήματος πριν από μια κλήρωση (παρατηρητήριο)."""
    p_main: np.ndarray                 # πυκνότητες κύριων (άθροισμα = 1)
    p_joker: np.ndarray                # πυκνότητες τζόκερ (άθροισμα = 1)
    amp_main: np.ndarray               # μιγαδικές πλάσεις κύριων (μήκος 50)
    amp_joker: np.ndarray              # μιγαδικές πλάσεις τζόκερ (μήκος 12)
    ent_main: np.ndarray               # μήτρα διεμπλοκής 50×50 (z-scores)
    ent_joker: np.ndarray              # μήτρα διεμπλοκής 12×12
    tunnel_main: np.ndarray            # δείκτες διόδευσης 0/1 (μήκος 50)
    tunnel_joker: np.ndarray           # δείκτες διόδευσης 0/1 (μήκος 12)
    n_draws: int = 0                   # πλήθος κληρώσεων που «έβλεπε» η κατάσταση
    meta: dict = field(default_factory=dict)


class QuantumEngine:
    """
    Χτίζει κβαντικές καταστάσεις από το ιστορικό και βαθμολογεί όλα τα
    κλαδιά σύμπαντος. Όλες οι πράξεις είναι ντετερμινιστικές.
    """

    def __init__(self, q: QuantumSettings):
        self.q = q

    # ── Δημιουργία κατάστασης ────────────────────────────────────────────────
    def build_state(self, history: Sequence[Draw]) -> QuantumState:
        """Κατασκευάζει την κατάσταση |ψ⟩ από όλο το διαθέσιμο ιστορικό."""
        if len(history) < 2:
            raise ValueError("Χρειάζονται τουλάχιστον 2 κληρώσεις ιστορικού.")

        lam = self.q.decay_lambda
        lam_e = self.q.ent_window

        p_main = np.zeros(N_MAINS)
        p_joker = np.zeros(N_JOKERS)
        c_main = np.zeros(N_MAINS)      # αποσυντιθέμενος μετρητής εμφανίσεων
        c_joker = np.zeros(N_JOKERS)
        co_main = np.zeros((N_MAINS, N_MAINS))
        co_joker = np.zeros((N_JOKERS, N_JOKERS))
        last_seen_main = np.full(N_MAINS, -1, dtype=int)
        last_seen_joker = np.full(N_JOKERS, -1, dtype=int)
        gap_sum_main = np.zeros(N_MAINS)
        gap_cnt_main = np.zeros(N_MAINS)
        w_eff = 0.0

        for idx, dr in enumerate(history):
            w = math.exp(-lam * idx)          # idx=0 → πιο πρόσφατη
            w2 = math.exp(-lam_e * idx)
            w_eff += w2
            mi = np.array(dr.mains) - 1
            jo = np.array(dr.jokers) - 1
            c_main[mi] += w
            c_joker[jo] += w2
            p_main[mi] += w
            p_joker[jo] += w2
            co_main[np.ix_(mi, mi)] += w2
            co_joker[np.ix_(jo, jo)] += w2
            for n in mi:
                if last_seen_main[n] >= 0:
                    gap_sum_main[n] += idx - last_seen_main[n]
                    gap_cnt_main[n] += 1
                last_seen_main[n] = idx
            for n in jo:
                last_seen_joker[n] = idx

        # ── Πυκνότητες (Born) ────────────────────────────────────────────────
        # Κανονικοποίηση ως προς τη δεξαμενή: οι τζόκερ του 2012 (1-8) δεν
        # πρέπει να «φαίνονται» πιο πιθανοί απλώς επειδή η δεξαμενή ήταν μικρή.
        p_main = p_main / p_main.sum()
        joker_scale = np.ones(N_JOKERS)
        for j in range(N_JOKERS):
            eras = []
            for idx, dr in enumerate(history):
                if (j + 1) <= dr.joker_max:
                    eras.append(math.exp(-lam_e * idx))
            joker_scale[j] = max(sum(eras), 1e-9)
        p_joker = c_joker / np.maximum(joker_scale, 1e-9)
        p_joker = p_joker / p_joker.sum()

        # ── Φάσεις (κυματική όψη) ────────────────────────────────────────────
        n = len(history)
        phi_main = np.zeros(N_MAINS)
        for i in range(N_MAINS):
            T = gap_sum_main[i] / gap_cnt_main[i] if gap_cnt_main[i] > 0 else n
            g = (n - 1 - last_seen_main[i]) if last_seen_main[i] >= 0 else T
            phi_main[i] = 2 * math.pi * ((g % max(T, 1.0)) / max(T, 1.0))
        # τζόκερ: απλή φάση από καθυστέρηση/μέση εμφάνιση
        phi_joker = 2 * math.pi * (np.arange(1, N_JOKERS + 1) / (N_JOKERS + 1))

        a_main = np.sqrt(p_main) * np.exp(1j * phi_main)
        a_joker = np.sqrt(p_joker) * np.exp(1j * phi_joker)

        # ── Μήτρες διεμπλοκής (z-scores συ-εμφανίσεων) ──────────────────────
        ent_main = self._entanglement(co_main, c_main, w_eff)
        ent_joker = self._entanglement(co_joker, c_joker, w_eff)

        # ── Κβαντική διόδευση (tunneling) ───────────────────────────────────
        tunnel_main = np.zeros(N_MAINS)
        for i in range(N_MAINS):
            T = gap_sum_main[i] / gap_cnt_main[i] if gap_cnt_main[i] > 0 else n
            g = (n - 1 - last_seen_main[i]) if last_seen_main[i] >= 0 else T
            if g > 2.5 * max(T, 1.0):
                tunnel_main[i] = 1.0
        tunnel_joker = np.zeros(N_JOKERS)
        seen_j = (n - 1 - last_seen_joker)
        tunnel_joker[seen_j > 25] = 1.0

        st = QuantumState(
            p_main=p_main, p_joker=p_joker,
            amp_main=a_main, amp_joker=a_joker,
            ent_main=ent_main, ent_joker=ent_joker,
            tunnel_main=tunnel_main, tunnel_joker=tunnel_joker,
            n_draws=n,
            meta={"decay_lambda": lam, "ent_window": lam_e},
        )
        log.info("Κβαντική κατάσταση |ψ⟩ έτοιμη: %d παρατηρήσεις, "
                 "τρόπος=%.2f, τυπική απόκλιση=%.2f", n, p_main.argmax() + 1,
                 float(p_main.std()))
        return st

    @staticmethod
    def _entanglement(co: np.ndarray, single: np.ndarray, w_eff: float) -> np.ndarray:
        """Μήτρα z-scores συ-εμφανίσεων (προσδοκία ανεξάρτητων συμβάντων)."""
        k = co.shape[0]
        total = co.sum() / 2.0
        if total <= 0 or w_eff <= 0:
            return np.zeros_like(co)
        p = single / w_eff
        exp = np.outer(p, p) * total
        with np.errstate(divide="ignore", invalid="ignore"):
            z = (co - exp) / np.sqrt(np.maximum(exp, 1.0))
        z = np.clip(z, -4.0, 4.0)
        np.fill_diagonal(z, 0.0)
        return z

    # ── Βαθμολόγηση κλαδιών σύμπαντος ────────────────────────────────────────
    def score_main_combos(self, st: QuantumState, top_k: int = 64) -> np.ndarray:
        """
        Βαθμολογεί και τα 2.118.760 πεντάδυμα (κύρια «κλαδιά») και επιστρέφει
        τα top_k καλύτερα σε μορφή [combo_index, (n1..n5), score] φθίνον.

        Σκορ = Σ (log p_i + w_tun·tun_i)  +  w_int·I(c)  +  w_ent·ΣE_ij
        όπου I(c) = 2·Σ_{i<j} √(p_i p_j)·cos(φ_i−φ_j)  [όρος αλληλεπίδρασης].

        Βελτιστοποιήσεις: cache όλων των συνδυασμών (combinadic), ενιαίο
        fancy-gather για αλληλεπίδραση+διεμπλοκή, argpartition ανά chunk.
        """
        q = self.q
        # log-πιθανότητες με ενσωματωμένη ώθηση διόδευσης (γλιτώνει ένα gather)
        logp_eff = np.log(np.maximum(st.p_main, 1e-12)) + q.w_tunneling * st.tunnel_main
        absm = np.sqrt(st.p_main)
        cosd = np.cos(np.angle(st.amp_main)[:, None] - np.angle(st.amp_main)[None, :])
        M = 2.0 * np.outer(absm, absm) * cosd
        np.fill_diagonal(M, 0.0)
        # στοίβα [50,50,2]: (αλληλεπίδραση, διεμπλοκή) → ένα gather αντί δύο
        P = np.stack([M, st.ent_main], axis=-1)

        pool_scores, pool_combos = [], []
        chunk = 150_000
        combos_all = self._all_main_combos()
        pairs_a, pairs_b = _PAIRS_5[:, 0], _PAIRS_5[:, 1]
        for start in range(0, C_50_5, chunk):
            cb = combos_all[start:start + chunk].astype(np.int64)   # 1-based (m,5)
            c0 = cb - 1
            lp = logp_eff[c0].sum(axis=1)
            pr = P[c0[:, pairs_a], c0[:, pairs_b]]                  # (m,10,2)
            score = lp + q.w_interference * pr[..., 0].sum(axis=1) \
                       + q.w_entanglement * pr[..., 1].sum(axis=1)
            k = min(top_k, score.size)
            idx = np.argpartition(-score, k - 1)[:k]
            pool_scores.append(score[idx])
            pool_combos.append(cb[idx])
        scores = np.concatenate(pool_scores)
        combos = np.vstack(pool_combos)
        order = np.argsort(-scores)
        return np.column_stack([combos[order], scores[order]])

    _MAIN_COMBOS_CACHE: dict = {}

    @classmethod
    def _all_main_combos(cls) -> np.ndarray:
        """Cache με και τα 2.118.760 πεντάδυμα (int16, 1-based, co-lex σειρά)."""
        if "combos" not in cls._MAIN_COMBOS_CACHE:
            cls._MAIN_COMBOS_CACHE["combos"] = cls._combos_chunk(0, C_50_5).astype(np.int16)
        return cls._MAIN_COMBOS_CACHE["combos"]

    _COMBINADIC_TABLES: dict = {}

    @classmethod
    def _comb_table(cls, pos: int) -> np.ndarray:
        """Πίνακας C(j, pos) για j=0..50 (combinadic σύστημα αρίθμησης)."""
        if pos not in cls._COMBINADIC_TABLES:
            cls._COMBINADIC_TABLES[pos] = np.array(
                [math.comb(j, pos) for j in range(N_MAINS + 1)], dtype=np.float64
            )
        return cls._COMBINADIC_TABLES[pos]

    @classmethod
    def _combos_chunk(cls, start: int, end: int) -> np.ndarray:
        """
        Αποκωδικοποιεί ranks [start,end) σε συνδυασμούς 5 από 50 (1-based)
        μέσω του combinadic συστήματος αρίθμησης (co-lex σειρά):
            rank = C(a1,1) + C(a2,2) + ... + C(a5,5),  a1<...<a5 (0-based)
        """
        r = np.arange(start, end, dtype=np.float64)
        out = np.empty((end - start, 5), dtype=np.int64)
        for pos in range(5, 0, -1):
            table = cls._comb_table(pos)
            idx = np.searchsorted(table, r, side="right") - 1
            idx = np.clip(idx, pos - 1, N_MAINS - 1)
            out[:, pos - 1] = idx          # 0-based στοιχείο
            r = r - table[idx]
        return out + 1                     # 1-based αριθμοί λοταρίας

    def score_joker_pairs(self, st: QuantumState) -> np.ndarray:
        """Βαθμολογεί τα 66 ζευγάρια τζόκερ → [pair, score] φθίνον."""
        q = self.q
        logp = np.log(np.maximum(st.p_joker, 1e-12))
        absm = np.sqrt(st.p_joker)
        cosd = np.cos(np.angle(st.amp_joker)[:, None] - np.angle(st.amp_joker)[None, :])
        M = 2.0 * np.outer(absm, absm) * cosd
        np.fill_diagonal(M, 0.0)
        rows = []
        for i, j in combinations(range(N_JOKERS), 2):
            s = logp[i] + logp[j] + q.w_interference * (M[i, j]) + q.w_entanglement * st.ent_joker[i, j]
            tun = st.tunnel_joker[i] + st.tunnel_joker[j]
            rows.append(((i + 1, j + 1), s + q.w_tunneling * tun))
        rows.sort(key=lambda x: -x[1])
        return rows

    def score_main_triples(self, st: QuantumState) -> np.ndarray:
        """Βαθμολογεί όλα τα C(50,3)=19.600 τρίδυμα για τον Σκελετό Β."""
        q = self.q
        logp_eff = np.log(np.maximum(st.p_main, 1e-12)) + q.w_tunneling * st.tunnel_main
        absm = np.sqrt(st.p_main)
        cosd = np.cos(np.angle(st.amp_main)[:, None] - np.angle(st.amp_main)[None, :])
        M = 2.0 * np.outer(absm, absm) * cosd
        np.fill_diagonal(M, 0.0)
        triples = np.array(list(combinations(range(N_MAINS), 3)))
        pm = _PAIRS_5[(_PAIRS_5[:, 0] < 3) & (_PAIRS_5[:, 1] < 3)]  # ζεύγη θέσεων τριάδας
        lp = logp_eff[triples].sum(axis=1)
        pin = M[triples[:, pm[:, 0]], triples[:, pm[:, 1]]].sum(axis=1)
        pen = st.ent_main[triples[:, pm[:, 0]], triples[:, pm[:, 1]]].sum(axis=1)
        scores = lp + q.w_interference * pin + q.w_entanglement * pen
        order = np.argsort(-scores)
        return np.column_stack([triples[order] + 1, scores[order]])

    # ── Πίνακες τοπικών πυκνοτήτων (marginals) ───────────────────────────────
    @staticmethod
    def top_numbers(st: QuantumState, k: int = 10) -> List[Tuple[int, float]]:
        """Οι k κορυφαίοι κύριοι αριθμοί με πυκνότητα πιθανότητας |a_i|²."""
        idx = np.argsort(-st.p_main)[:k]
        return [(int(i) + 1, float(st.p_main[i])) for i in idx]

    @staticmethod
    def top_jokers(st: QuantumState, k: int = 4) -> List[Tuple[int, float]]:
        idx = np.argsort(-st.p_joker)[:k]
        return [(int(i) + 1, float(st.p_joker[i])) for i in idx]

    @staticmethod
    def entanglement_partners(st: QuantumState, num: int, k: int = 3) -> List[int]:
        """Οι πιο «διεμπλεκόμενοι» εταίροι ενός αριθμού (1-based)."""
        row = st.ent_main[num - 1].copy()
        row[num - 1] = -np.inf
        idx = np.argsort(-row)[:k]
        return [int(i) + 1 for i in idx]

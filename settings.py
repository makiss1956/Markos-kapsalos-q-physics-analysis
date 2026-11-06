"""
Κεντρική διαχείριση ρυθμίσεων (config.yaml + .env).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml

# ── Διαδρομές έργου ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
HISTORY_CSV = DATA_DIR / "eurojackpot_history.csv"
PREDICTIONS_JSONL = REPORTS_DIR / "predictions_history.jsonl"

for _d in (DATA_DIR, REPORTS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_env_file() -> None:
    """Φορτώνει απλά ζεύγη KEY=VALUE από το .env (χωρίς εξωτερική βιβλιοθήκη)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass  # αν αποτύχει η ανάγνωση, συνεχίζουμε με τις υπάρχουσες μεταβλητές


_load_env_file()


@dataclass
class EmailSettings:
    """Ρυθμίσεις αποστολής email μέσω Gmail SMTP."""
    enabled: bool = True
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    user: str = ""          # GMAIL_USER
    app_password: str = ""  # GMAIL_APP_PASSWORD (App Password, όχι ο κύριος κωδικός!)
    recipient: str = ""     # EMAIL_TO

    @classmethod
    def from_env(cls) -> "EmailSettings":
        return cls(
            enabled=os.getenv("EMAIL_ENABLED", "true").lower() != "false",
            smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("GMAIL_USER", ""),
            app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
            recipient=os.getenv("EMAIL_TO", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.user and self.app_password and self.recipient)


@dataclass
class QuantumSettings:
    """Βάρη και παράμετροι του κβαντικού μοντέλου."""
    decay_lambda: float = 0.0012      # ρυθμός αποσύνθεσης πλάσης ανά κλήρωση (half-life ~ 577)
    ent_window: float = 0.0025        # αποσύνθεσης μήτρας διεμπλοκής (half-life ~ 277)
    w_interference: float = 1.0       # βάρος όρου αλληλεπίδρασης (κύμα-σωματίδιο)
    w_entanglement: float = 0.35      # βάρος όρου διεμπλοκής (συ-εμφανίσεις)
    w_tunneling: float = 0.06         # σμικρή ώθηση «κβαντικής διόδευσης» υπερ-αλυχισμένων
    alt_tickets: int = 2              # εναλλακτικά σύνολα 5+2 (2ο & 3ο «κλαδί σύμπαντος»)
    min_branch_distance: int = 2      # ελάχ. διαφορά εναλλακτικών από τον Σκελετό Α


@dataclass
class Settings:
    """Συνολικές ρυθμίσεις εφαρμογής."""
    quantum: QuantumSettings = field(default_factory=QuantumSettings)
    email: EmailSettings = field(default_factory=EmailSettings.from_env)
    warmup_draws: int = 300           # ελάχ. ιστορικό πριν την πρώτη πρόβλεψη
    backtest_depth: int = 0           # 0 = όλο το διαθέσιμο ιστορικό
    cron_times: str = "22:30 Τρίτη & Παρασκευή"  # πληροφοριακό
    timezone: str = "Europe/Athens"

    @classmethod
    def load(cls) -> "Settings":
        """Φορτώνει config.yaml (αν υπάρχει) και εφαρμόζει επικαλύψεις."""
        s = cls()
        cfg_path = PROJECT_ROOT / "config.yaml"
        if cfg_path.exists():
            try:
                raw: Dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                raw = {}
            q = raw.get("quantum", {}) or {}
            for key, val in q.items():
                if hasattr(s.quantum, key) and val is not None:
                    setattr(s.quantum, key, type(getattr(s.quantum, key))(val))
            bt = raw.get("backtest", {}) or {}
            if "depth" in bt:
                s.backtest_depth = int(bt["depth"] or 0)
            if "warmup_draws" in bt:
                s.warmup_draws = int(bt["warmup_draws"] or 300)
            tz = raw.get("timezone")
            if tz:
                s.timezone = str(tz)
        return s


SETTINGS = Settings.load()

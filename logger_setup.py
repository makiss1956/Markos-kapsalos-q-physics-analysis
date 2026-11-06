"""
Ρύθμιση καταγραφής (logging) με περιστρεφόμενο αρχείο + κονσόλα.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from quantum_lottery.settings import LOGS_DIR

_LOG_FILE = LOGS_DIR / "quantum.log"
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-18s | %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO, console: bool = True) -> logging.Handler:
    """Εγκαθιστά το root logger μία μόνο φορά και επιστρέφει τον file handler."""
    global _configured
    root = logging.getLogger()
    if _configured:
        return root.handlers[0] if root.handlers else logging.NullHandler()

    root.setLevel(level)
    fmt = logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    file_h = RotatingFileHandler(_LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_h.setFormatter(fmt)
    root.addHandler(file_h)

    if console:
        con_h = logging.StreamHandler(sys.stdout)
        con_h.setFormatter(fmt)
        root.addHandler(con_h)

    _configured = True
    return file_h


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

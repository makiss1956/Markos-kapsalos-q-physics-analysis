"""
Αποστολέας Email (Gmail SMTP)
=============================

Στέλνει την πρόβλεψη + τη σύγκριση σε όμορφο HTML email μέσω Gmail.
Χρειάζεται App Password (όχι τον κύριο κωδικό του λογαριασμού) —
δες INSTALL_GUIDE_LINUX.md, ενότητα «Gmail App Password».
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from quantum_lottery.logger_setup import get_logger
from quantum_lottery.settings import SETTINGS

log = get_logger("Emailer")


def send_html(subject: str, html: str, fallback_text: str = "",
              save_to: Optional[Path] = None) -> bool:
    """
    Αποστολή HTML email μέσω Gmail SMTP.
    Αν δεν υπάρχει ρύθμιση, αποθηκεύει το HTML τοπικά και επιστρέφει False.
    """
    em = SETTINGS.email
    if save_to:
        save_to.write_text(html, encoding="utf-8")
        log.info("Η HTML αναφορά αποθηκεύτηκε: %s", save_to)

    if not em.enabled:
        log.info("Το email είναι απενεργοποιημένο (EMAIL_ENABLED=false).")
        return False
    if not em.is_configured:
        log.warning("Στοιχεία Gmail μη ρυθμισμένα (.env) — η αναφορά αποθηκεύτηκε μόνο τοπικά.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = em.user
    msg["To"] = em.recipient
    msg.attach(MIMEText(fallback_text or "Δες το επισυναπτόμενο HTML.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(em.smtp_server, em.smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(em.user, em.app_password)
            server.sendmail(em.user, [em.recipient], msg.as_string())
        log.info("Email εστάλη στο %s ✔", em.recipient)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Αποτυχία αποστολής email: %s", exc)
        return False

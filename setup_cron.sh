#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Quantum Lottery Analysis V2 — Εγκατάσταση cron για Linux / Raspberry Pi
#
# Εκτέλεση:  bash setup_cron.sh
# Τι κάνει: προσθέτει cron job που τρέχει το `auto` κάθε Τρίτη & Παρασκευή
#           στις 22:30 (ώρα Ελλάδας) — μετά τις κληρώσεις των 21:00.
# Αφαίρεση: crontab -e  (σβήσε τη γραμμή QUANTUM-LOTTERY)
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
JOB="30 22 * * 2,5 cd $DIR && $PYTHON $DIR/quantum_lottery.py auto >> $DIR/logs/cron.log 2>&1  # QUANTUM-LOTTERY"

# Η ώρα του συστήματος πρέπει να είναι Europe/Athens (ή οποιαδήποτε ζώνη
# όπου 22:30 σημαίνει "μετά την κλήρωση"). Έλεγχος:
if command -v timedatectl >/dev/null 2>&1; then
  echo "⏰ Ζώνη συστήματος: $(timedatectl show -p Timezone --value 2>/dev/null || date +%Z)"
fi

( crontab -l 2>/dev/null | grep -v "QUANTUM-LOTTERY" ; echo "$JOB" ) | crontab -
echo "✔ Cron εγκαταστάθηκε: κάθε Τρίτη & Παρασκευή 22:30"
echo "  Έλεγχος: crontab -l"
echo "  Logs:    $DIR/logs/cron.log"

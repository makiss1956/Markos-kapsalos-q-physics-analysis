# 📖 Αναλυτικές Οδηγίες Εγκατάστασης — Linux / Raspberry Pi

Αυτός ο οδηγός είναι γραμμένος για κάποιον που θέλει να κάνει **κάθε βήμα
με το χέρι**, χωρίς υποθέσεις. Αν κολλήσεις κάπου, δες την ενότητα
«Αντιμετώπιση προβλημάτων» στο τέλος.

---

## 1️⃣ Προαπαιτούμενα

```bash
# Έλεγχος Python (χρειάζεται 3.9 ή νεότερη):
python3 --version

# Έλεγχος pip:
pip3 --version
# αν λείπει:  sudo apt update && sudo apt install -y python3-pip
```

## 2️⃣ Εγκατάσταση του έργου

```bash
# Τοποθέτηση σε μόνιμο φάκελο (μπορείς να διαλέξεις όποιο θέλεις):
mv Quantum-Lottery-Analysis-V2 ~/quantum_lottery
cd ~/quantum_lottery

# Εξαρτήσεις (numpy, requests, PyYAML):
pip3 install -r requirements.txt
# Σε Raspberry Pi/Raspbian αν ζητήσει:  pip3 install --break-system-packages -r requirements.txt
```

## 3️⃣ Πρώτη εκτέλεση & έλεγχος δεδομένων

```bash
python3 quantum_lottery.py status
# Αναμένεις:
#   ✔ Ιστορικό: 1004 κληρώσεις (τελευταία 03/11/2026)   ← ή νεότερη
#   ✔ Επόμενη κλήρωση: … (Τρίτη ή Παρασκευή)
python3 quantum_lottery.py fetch
# Κατεβάζει τυχόν νέες κληρώσεις από τις πηγές.
```

Το ιστορικό **συμπεριλαμβάνεται ήδη** στο ZIP (`data/eurojackpot_history.csv`),
οπότε το σύστημα δουλεύει ακόμα και χωρίς internet· με internet ενημερώνεται
αυτόματα από:
1. `dev-baris/lottery-archive` (πλήρες CSV, ενημερώνεται καθημερινά), και
2. `eurojackpot.org` (επίσημη σελίδα — για επαλήθευση/συμπλήρωση).

## 4️⃣ Gmail App Password (πρέπει μία φορά, 2 λεπτά)

Το Gmail **δεν δέχεται** τον κύριο κωδικό σου από προγράμματα. Χρειάζεται
**App Password** (κωδικός εφαρμογής 16 χαρακτήρων):

1. Πήγαινε στον λογαριασμό Google: https://myaccount.google.com/security
2. Βεβαιώσου ότι είναι ενεργοποιημένη η **Επαλήθευση 2 βημάτων**
   (αν όχι — ενεργοποίησέ τη, είναι υποχρεωτική για App Passwords).
3. Πήγαινε στο https://myaccount.google.com/apppasswords
4. Δώσε όνομα π.χ. `quantum-lottery` → πάτα **Δημιουργία**.
5. Θα δεις κωδικό **16 χαρακτήρων** π.χ. `abcd efgh ijkl mnop`.
   Αντίγραψέ τον (χωρίς κενά).

## 5️⃣ Ρύθμιση αρχείου .env

```bash
cp .env.example .env
nano .env
```

Συμπλήρωσε:

```
GMAIL_USER=το.email σου@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
EMAIL_TO=όπου.θες.να.φτάνει@gmail.com
```

(Το App Password γράφεται **χωρίς κενά**. Το `.env` δεν ανεβαίνει ποτέ στο git.)

Δοκιμή:

```bash
python3 quantum_lottery.py test-email
# → "✔ Το email εστάλη!" — έλεγξε τα εισερχόμενά σου
```

## 6️⃣ Πρώτη πρόβλεψη

```bash
python3 quantum_lottery.py predict
```

Θα δεις στην κονσόλα:

```
  ΠΡΟΒΛΕΨΗ για την κλήρωση 06/11/2026
  Σκελετός Α (5+2):   1 17 18 35 49  ✦ 11 12
  Εναλλακτικό #1:    13 17 35 41 49  ✦ 10 12
  Εναλλακτικό #2:     1 18 19 35 41  ✦  9 12
  Σκελετός Β (3+1):   1 35 49  ✦  5
  Κλασικό (5+2):      1  3  8 13 27  ✦  2  6
  Εστάλη email: ναι
```

και το ίδιο σε όμορφο HTML στο email σου και στο `reports/prediction_ΗΜΕΡΟΜΗΝΙΑ.html`.

## 7️⃣ Αυτόματη λειτουργία (cron) — Τρίτη & Παρασκευή 22:30

```bash
bash setup_cron.sh
```

Αυτό εγκαθιστά την εντολή:

```
30 22 * * 2,5 cd ~/quantum_lottery && python3 quantum_lottery.py auto >> logs/cron.log 2>&1
```

- Οι κληρώσεις γίνονται **21:00** (Τρίτη & Παρασκευή)· τα αποτελέσματα
  δημοσιεύονται ~21:30-22:00. Στις **22:30** το σύστημα:
  1. κατεβάζει το αποτέλεσμα της βραδινής κλήρωσης,
  2. συγκρίνει την πρόβλεψή του (**ποιο βραβείο έπιασε**),
  3. εκδίδει νέα πρόβλεψη για την επόμενη κλήρωση,
  4. σου στέλνει email με ΟΛΑ τα παραπάνω.
- Έλεγχος: `crontab -l` • Καταγραφές: `logs/cron.log` και `logs/quantum.log`
- Αφαίρεση: `crontab -e` (σβήσε τη γραμμή με το σχόλιο `QUANTUM-LOTTERY`)

> ⏰ Η ώρα του συστήματος πρέπει να είναι σωστή: `timedatectl set-timezone Europe/Athens`

## 8️⃣ Backtest (αξιολόγηση σε όλο το ιστορικό)

```bash
python3 quantum_lottery.py backtest            # όλο το ιστορικό (~15 λεπτά)
python3 quantum_lottery.py backtest --depth 100  # μόνο τις τελευταίες 100
```

Βγάζει πίνακα: πόσες «συμμετοχές» έγιναν, πόσα βραβεία και σε ποιες κατηγορίες,
για **quantum-A / quantum-B / classic-A / classic-B**. Το αποτέλεσμα αποθηκεύεται
στο `reports/backtest_ΗΜΕΡΟΜΗΝΙΑ.md`.

## 9️⃣ Στατιστικά & βελτιώσεις

```bash
python3 quantum_lottery.py report
```

Ό,τι έχει γίνει ποτέ από το σύστημα βρίσκεται σε:
- `logs/quantum.log` — τεχνικό log (περιστρεφόμενο, 2MB×5)
- `reports/predictions_history.jsonl` — **μόνιμο αρχείο προβλέψεων/αποτελεσμάτων**
  (μια γραμμή ανά γεγονός — ιδανικό για μελλοντική ανάλυση & βελτίωση μοντέλου)

Για προσαρμογή του μοντέλου: άλλαξε βάρη στο `config.yaml`
(`w_interference`, `w_entanglement`, `w_tunneling`, `decay_lambda`) και
ξανατρέξε το backtest για σύγκριση — έτσι γίνεται τεκμηριωμένη βελτίωση.

---

## 🛠 Αντιμετώπιση προβλημάτων

| Πρόβλημα | Λύση |
|---|---|
| `✖ Δεν στάλθηκε` στο test-email | Έλεγξε GMAIL_APP_PASSWORD (16 χαρακτήρες, χωρίς κενά), ενεργή 2FA, και `less logs/quantum.log` |
| `535-5.7.8 Username and Password not accepted` | Λάθος App Password ή δεν είναι ενεργή η 2FA |
| `ModuleNotFoundError: numpy` | `pip3 install -r requirements.txt` (ή με `--break-system-packages`) |
| «Ανεπαρκές ιστορικό» | `python3 quantum_lottery.py fetch` — έλεγξε internet |
| Cron δεν τρέχει | `crontab -l` να περιέχει τη γραμμή· `logs/cron.log` για σφάλματα· απόλυτο path python3 (`command -v python3`) |
| Ώρα λάθος | `timedatectl set-timezone Europe/Athens` |
| Θέλω να αλλάξω ώρα cron | Επεξεργάσου το `setup_cron.sh` (π.χ. `30 23 * * 2,5` για 23:30) και ξανατρέξε το |

---

*Quantum Lottery Analysis v2.0 — Markos Kapsalos — εκπαιδευτική χρήση, πάντα υπεύθυνο παιχνίδι.*

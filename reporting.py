"""
Κατασκευαστής Αναφορών HTML (Reporting)
=======================================

Χτίζει την όμορφη HTML αναφορά που πηγαίνει στο email και αποθηκεύεται
στον φάκελο reports/. Όλα τα στυλ είναι inline ώστε να εμφανίζεται σωστά
και στο Gmail.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from quantum_lottery.comparison import ComparisonResult
from quantum_lottery.predictor import Prediction

CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;background:#0b1026;color:#e8ecf7;margin:0;padding:24px;}
.wrap{max-width:760px;margin:0 auto;}
h1{font-size:26px;color:#9fd0ff;margin:0 0 4px;}
h2{font-size:18px;color:#9fd0ff;border-bottom:1px solid #2a3a6b;padding-bottom:6px;margin-top:28px;}
.sub{color:#8fa0c9;font-size:13px;margin-bottom:18px;}
.card{background:#131a38;border:1px solid #2a3a6b;border-radius:14px;padding:18px 20px;margin:14px 0;}
.balls{margin:10px 0;font-size:0;}
.ball{display:inline-block;width:46px;height:46px;line-height:46px;margin:0 8px 8px 0;border-radius:50%;
 text-align:center;font-weight:700;font-size:18px;color:#0b1026;background:#ffd76a;}
.ball.star{background:#9fd0ff;}
.ball.hit{outline:3px solid #58e07f;}
.tag{display:inline-block;background:#22305e;border-radius:20px;padding:3px 12px;font-size:12px;color:#9fd0ff;margin-right:8px;}
table{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0;}
th{background:#1b2549;color:#9fd0ff;text-align:left;padding:8px 10px;}
td{padding:7px 10px;border-top:1px solid #232f5c;}
.balls-tbl{margin:6px 0;}
.balls-tbl td{border-top:none;padding:0 8px 8px 0;background:transparent;}
.tier{color:#58e07f;font-weight:700;}
.muted{color:#8fa0c9;}
.small{font-size:12px;color:#8fa0c9;}
.footer{margin-top:26px;font-size:11px;color:#5d6b96;line-height:1.5;border-top:1px solid #232f5c;padding-top:12px;}
"""


def _balls(numbers, jokers=None, hit_mains=(), hit_jokers=()) -> str:
    """
    Σφαίρες αριθμών με πλήρη inline στυλ (αποδίδονται σωστά σε Gmail,
    Outlook, Thunderbird — χωρίς εξάρτηση από <style>).
    """
    GOLD, BLUE, GREEN = "#ffd76a", "#9fd0ff", "#58e07f"

    def cell(n: int, color: str, hit: bool) -> str:
        ring = f"border:3px solid {GREEN};" if hit else ""
        return ('<td style="width:52px;min-width:52px;height:52px;text-align:center;'
                f'vertical-align:middle;background:{color};border-radius:26px;{ring}'
                'font-weight:bold;font-size:19px;color:#0b1026;padding:0;">'
                f'{n}</td>'
                '<td style="width:9px;min-width:9px;"></td>')

    cells = [cell(n, GOLD, n in hit_mains) for n in numbers]
    cells += [cell(n, BLUE, n in hit_jokers) for n in (jokers or [])]
    return ('<table style="border-collapse:separate;margin:8px 0;"><tr>'
            + "".join(cells) + "</tr></table>")


def _comparison_row(c: ComparisonResult) -> str:
    tier_txt = f'<span class="tier">✔ {c.tier_label}</span>' if c.tier else '<span class="muted">—</span>'
    one_in = f"1 στο {c.one_in:,.0f}" if c.one_in != float("inf") else "—"
    return (f"<tr><td>{c.engine.upper()} / Σκελετός {c.skeleton}</td>"
            f"<td>{c.mains_hit} κύριοι + {c.jokers_hit} τζόκερ</td>"
            f"<td>{tier_txt}</td><td class='muted'>{one_in}</td></tr>")


def build_html(pred: Prediction,
               comparisons: Optional[List[ComparisonResult]] = None,
               stats: Optional[Dict] = None,
               next_draw: Optional[date] = None) -> str:
    """Χτίζει την πλήρη HTML αναφορά πρόβλεψης."""
    comparisons = comparisons or []
    fmt = lambda d: d.strftime("%d/%m/%Y")

    alt_rows = ""
    for a in pred.alternatives:
        alt_rows += ("<tr><td>κλαδί #" + str(a["rank"]) + "</td><td>" +
                     _balls(a["mains"], a["jokers"]) + "</td></tr>")

    top_rows = "".join(
        f"<tr><td><b>{n}</b></td><td>{p * 100:.3f}%</td>"
        f"<td class='muted'>διεμπλοκή: {', '.join(str(x) for x in pred.entanglement_info.get(n, [])) or '—'}</td></tr>"
        for n, p in pred.top_mains)

    comp_html = ""
    if comparisons:
        comp_html = ("<h2>🔍 Σύγκριση με την προηγούμενη κλήρωση</h2><table>"
                     "<tr><th>Πρόβλεψη</th><th>Επιτυχίες</th><th>Βραβείο</th><th>Τύχη</th></tr>" +
                     "".join(_comparison_row(c) for c in comparisons) + "</table>")

    stats_html = ""
    if stats and stats.get("tickets"):
        rows = ""
        for key, cnt in sorted(stats["tickets"].items()):
            tiers = stats["tiers"].get(key, {})
            won = sum(v for k, v in tiers.items() if k != "none")
            rows += f"<tr><td>{key}</td><td>{cnt}</td><td>{won}</td></tr>"
        stats_html = ("<h2>📊 Συσσωρευμένα στατιστικά (αρχή: εγκατάσταση)</h2>"
                      f"<table><tr><th>Μοντέλο</th><th>Συμμετοχές</th><th>Βραβεία</th></tr>{rows}</table>")

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{CSS}</style></head><body><div class="wrap">
<h1>🔮 Quantum EuroJackpot</h1>
<div class="sub">Κβαντική ανάλυση • 139.838.160 σύμπαντα σαρώθηκαν • στοίχιση για κλήρωση {fmt(pred.target_date)}</div>

<div class="card">
<span class="tag">ΣΚΕΛΕΤΟΣ Α — Πλήρες Σύμπαν (5+2)</span>
{_balls(pred.skeleton_a, pred.jokers_a)}
<div class="small">βαρύτητα κλαδιού: {pred.branch_scores.get('skeleton_a', 0):.4f}</div>
</div>

<div class="card">
<span class="tag">ΕΝΑΛΛΑΚΤΙΚΑ ΚΛΑΔΙΑ ΣΥΜΠΑΝΤΟΣ</span>
<table>{alt_rows}</table>
</div>

<div class="card">
<span class="tag">ΣΚΕΛΕΤΟΣ Β — Κατάρρευση Παρατήρησης (3+1)</span>
{_balls(pred.skeleton_b, [pred.joker_b])}
<div class="small">βαρύτητα κλαδιού: {pred.branch_scores.get('skeleton_b', 0):.4f}</div>
</div>

<h2>📈 Πίνακας top-10 (πυκνότητες πιθανότητας |ψ|²)</h2>
<table><tr><th>Αριθμός</th><th>Πυκνότητα</th><th>Σημείωση</th></tr>{top_rows}</table>
<div class="small">Τζόκερ (top-4): {', '.join(f'{n} ({p*100:.2f}%)' for n, p in pred.top_jokers)}</div>

{comp_html}
{stats_html}

<h2>🧪 Κλασικό μοντέλο (για σύγκριση)</h2>
<div class="card">
{_balls(pred.classic_a, pred.classic_jokers)}
<div class="small">3+1: {', '.join(map(str, pred.classic_b))} + {pred.classic_joker_b}</div>
</div>

<div class="footer">
<b>Σημαντικό:</b> Οι κληρώσεις του EuroJackpot είναι ανεξάρτητα τυχαία συμβάντα.
Το κβαντικό μοντέλο είναι ερευνητικό/εκπαιδευτικό εργαλείο και ΔΕΝ αυξάνει τις
πιθανότητες νίκης. Το σύστημα καταγράφει κάθε πρόβλεψη και κάθε αποτέλεσμα στο
μονιμό ιστορικό (predictions_history.jsonl) ώστε να μελετώνται οι επιδόσεις σε βάθος χρόνου.<br>
Quantum Lottery Analysis v2.0 • Markos Kapsalos • υπεύθυνο παιχνίδι πάντα.
</div>
</div></body></html>"""
    return html

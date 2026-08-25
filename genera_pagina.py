"""
Genera docs/index.html: una pagina statica, leggibile da qualsiasi
browser (anche da telefono), che mostra lo stato attuale di Salvabot.

Va lanciata dopo run_ciclo.py (lo fa già il workflow di GitHub Actions).
Non serve un vero "server web": e' una pagina statica, ospitabile
gratuitamente con GitHub Pages.
"""

import json
from pathlib import Path
from urllib.parse import quote

import config
import notifications
import settings_store
import state_store

CARTELLA_OUTPUT = Path("docs")
FILE_OUTPUT = CARTELLA_OUTPUT / "index.html"


def _link_azione(azione: str, id_notifica: int, corpo: str = "") -> str:
    """
    Costruisce il link che apre una issue GitHub pre-compilata: e' cosi'
    che un tocco sul telefono diventa una richiesta che il workflow di
    conferma poi legge ed esegue automaticamente.
    """
    titolo = quote(f"salvabot:{azione}:{id_notifica}")
    corpo_codificato = quote(corpo)
    return (
        f"https://github.com/{config.GITHUB_REPO}/issues/new"
        f"?title={titolo}&body={corpo_codificato}&labels=salvabot-azione"
    )


def _bottoni_per_notifica(n: dict) -> str:
    if not n["richiede_conferma"]:
        return ""

    corpo_default = ""
    if n["tipo"] == "salvadanaio":
        corpo_default = "Importo da mettere nel salvadanaio (modifica il numero se vuoi): 400"
    elif n["tipo"] == "espansione":
        corpo_default = "Quota da destinare a crypto/azioni (modifica il numero se vuoi): 50"

    link_conferma = _link_azione("conferma", n["id"], corpo_default)
    link_ignora = _link_azione("ignora", n["id"])

    return (
        f'<div class="bottoni">'
        f'<a class="bottone secondario" href="{link_ignora}" target="_blank">Non ora</a>'
        f'<a class="bottone primario" href="{link_conferma}" target="_blank">Conferma</a>'
        f'</div>'
    )


def _icona(nome: str, colore: str = "currentColor") -> str:
    """Piccole icone SVG minimali (stile lineare), al posto delle emoji."""
    icone = {
        "salvadanaio": (
            f'<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="{colore}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M4 12c0-3.5 3-6 7-6h4a4 4 0 0 1 4 4v1l2 1-2 1v1a3 3 0 0 1-3 3h-1v2h-3v-2H9a5 5 0 0 1-5-5Z"/>'
            f'<circle cx="15" cy="10" r="0.6" fill="{colore}"/>'
            f'<path d="M7 9 5 7"/>'
            f'</svg>'
        ),
        "su": (
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{colore}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="3 17 9 11 13 15 21 6"/><polyline points="15 6 21 6 21 12"/>'
            f'</svg>'
        ),
        "giu": (
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{colore}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="3 7 9 13 13 9 21 18"/><polyline points="15 18 21 18 21 12"/>'
            f'</svg>'
        ),
        "pari": (
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{colore}" '
            f'stroke-width="2" stroke-linecap="round">'
            f'<line x1="4" y1="12" x2="20" y2="12"/>'
            f'</svg>'
        ),
    }
    return icone.get(nome, "")


def _sparkline(storico_saldo: list[float], colore: str = "#1e7d3c") -> str:
    """Piccolo grafico a linea (SVG) dell'andamento del saldo, senza librerie esterne."""
    valori = storico_saldo[-30:]  # ultimi 30 punti, per restare leggibile
    if len(valori) < 2:
        return '<p class="muto" style="margin-top:8px;">Non ci sono ancora abbastanza dati per un grafico.</p>'

    larghezza, altezza = 340, 70
    minimo, massimo = min(valori), max(valori)
    intervallo = (massimo - minimo) or 1.0

    punti = []
    for i, v in enumerate(valori):
        x = (i / (len(valori) - 1)) * larghezza
        y = altezza - ((v - minimo) / intervallo) * (altezza - 10) - 5
        punti.append(f"{x:.1f},{y:.1f}")
    polilinea = " ".join(punti)

    return (
        f'<svg viewBox="0 0 {larghezza} {altezza}" width="100%" height="{altezza}" '
        f'preserveAspectRatio="none" style="margin-top: 10px;">'
        f'<polyline points="{polilinea}" fill="none" stroke="{colore}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def _badge_trend(direzione: str) -> str:
    if direzione == "crescita":
        return f'<span class="badge verde">{_icona("su", "#1e7d3c")} In crescita</span>'
    if direzione == "calo":
        return f'<span class="badge ambra">{_icona("giu", "#9a6a11")} In calo</span>'
    return f'<span class="badge grigio">{_icona("pari", "#555")} Stabile</span>'


def genera() -> None:
    CARTELLA_OUTPUT.mkdir(exist_ok=True)

    stato_e_portafoglio = state_store.carica_stato()
    impostazioni = settings_store.carica_impostazioni()
    notifiche_non_lette = notifications.non_lette()

    if stato_e_portafoglio is None:
        saldo, salvadanaio, direzione, giorni_trend, posizioni, storico = 0.0, 0.0, "stabile", 0, {}, []
    else:
        stato, portafoglio = stato_e_portafoglio
        saldo = portafoglio.saldo_investito
        salvadanaio = portafoglio.salvadanaio
        direzione, giorni_trend = portafoglio.giorni_di_trend()
        posizioni = stato.posizioni
        storico = portafoglio.storico_saldo

    colore_grafico = "#c9432b" if direzione == "calo" else "#1e7d3c"
    grafico_saldo = _sparkline(storico, colore_grafico)

    righe_posizioni = "".join(
        f'<div class="riga"><span>{ticker}</span><span>{p.quota_investita:.2f} EUR</span></div>'
        for ticker, p in posizioni.items()
    ) or '<p class="muto">Nessuna posizione aperta al momento.</p>'

    righe_notifiche = "".join(
        f'<div class="notifica {"conferma" if n["richiede_conferma"] else ""}">'
        f'<p>{n["messaggio"]}</p><span class="data">{n["data"]}</span>'
        f'{_bottoni_per_notifica(n)}'
        f'</div>'
        for n in notifiche_non_lette
    ) or '<p class="muto">Nessuna notifica in sospeso.</p>'

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Salvabot</title>
<style>
  body {{
    font-family: -apple-system, system-ui, sans-serif;
    background: #f4f5f4;
    margin: 0;
    padding: 1.5rem 1rem;
    color: #1a1a1a;
  }}
  .card {{
    max-width: 400px;
    margin: 0 auto 1rem;
    background: #ffffff;
    border-radius: 14px;
    border: 1px solid #e4e4e4;
    padding: 1.25rem;
  }}
  h1 {{ font-size: 1.1rem; margin: 0 0 1rem; display: flex; align-items: center; gap: 8px; }}
  .saldo {{ text-align: center; margin-bottom: 1rem; }}
  .saldo .valore {{ font-size: 2.1rem; font-weight: 600; margin: 0; }}
  .saldo .etichetta {{ font-size: 0.8rem; color: #666; margin: 0 0 4px; }}
  .badge {{ display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 500; }}
  .badge.verde {{ background: #e3f5e9; color: #1e7d3c; }}
  .badge.ambra {{ background: #fdf1dd; color: #9a6a11; }}
  .badge.grigio {{ background: #eee; color: #555; }}
  .sezione {{ margin-top: 1rem; }}
  .sezione h2 {{ font-size: 0.8rem; color: #888; margin: 0 0 8px; text-transform: uppercase; letter-spacing: .03em; }}
  .riga {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; }}
  .muto {{ color: #999; font-size: 0.85rem; }}
  .notifica {{ background: #f7f7f7; border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; font-size: 0.85rem; }}
  .notifica.conferma {{ background: #fdf1dd; }}
  .notifica .data {{ color: #999; font-size: 0.75rem; }}
  .bottoni {{ display: flex; gap: 8px; margin-top: 10px; }}
  .bottone {{ flex: 1; text-align: center; padding: 8px; border-radius: 8px; font-size: 0.85rem;
             font-weight: 500; text-decoration: none; }}
  .bottone.primario {{ background: #1e7d3c; color: #fff; }}
  .bottone.secondario {{ background: #eee; color: #444; }}
  .impostazioni .riga span:last-child {{ font-weight: 500; }}
</style>
</head>
<body>

  <div class="card">
    <h1>{_icona('salvadanaio', '#1e7d3c')} Salvabot</h1>
    <div class="saldo">
      <p class="etichetta">Saldo investito</p>
      <p class="valore">{saldo:.2f} €</p>
      {_badge_trend(direzione)}
    </div>
    {grafico_saldo}
    <div class="riga" style="margin-top: 10px;"><span>Salvadanaio</span><span>{salvadanaio:.2f} €</span></div>
  </div>

  <div class="card sezione">
    <h2>Notifiche</h2>
    {righe_notifiche}
  </div>

  <div class="card sezione">
    <h2>Posizioni aperte</h2>
    {righe_posizioni}
  </div>

  <div class="card sezione impostazioni">
    <h2>Impostazioni attuali</h2>
    <div class="riga"><span>Cautela</span><span>{impostazioni['CAUTELA']}</span></div>
    <div class="riga"><span>Stop-loss</span><span>{impostazioni['STOP_LOSS_PCT']:.0%}</span></div>
    <div class="riga"><span>Take-profit</span><span>{impostazioni['TAKE_PROFIT_PCT']:.0%}</span></div>
  </div>

  <p class="muto" style="text-align:center; font-size: 0.75rem;">
    Pagina generata automaticamente ad ogni ciclo. "Conferma"/"Non ora" aprono una richiesta
    su GitHub (serve essere loggati): viene gestita da sola entro qualche minuto.
  </p>

</body>
</html>
"""
    FILE_OUTPUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    genera()
    print(f"Pagina generata: {FILE_OUTPUT}")

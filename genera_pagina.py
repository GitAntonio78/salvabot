"""
Genera docs/index.html: una pagina statica, leggibile da qualsiasi
browser (anche da telefono), che mostra lo stato attuale di Salvabot.

Va lanciata dopo run_ciclo.py (lo fa già il workflow di GitHub Actions).
Non serve un vero "server web": e' una pagina statica, ospitabile
gratuitamente con GitHub Pages.
"""

import json
from datetime import datetime
from html import escape
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
        "evento": (
            '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#9a6a11" '
            'stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="8"/>'
            '<circle cx="12" cy="12" r="2.6" fill="#9a6a11"/></svg>'
        ),
        "pari": (
            f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="{colore}" '
            f'stroke-width="2" stroke-linecap="round">'
            f'<line x1="4" y1="12" x2="20" y2="12"/>'
            f'</svg>'
        ),
    }
    return icone.get(nome, "")


def _sparkline(storico_punti: list[dict], colore: str = "#1e7d3c") -> str:
    """
    Piccolo grafico a linea con puntini (SVG), sugli ultimi 10 passaggi di
    Salvabot (storico_punti e' gia' limitato a 10 a monte, nel portafoglio).
    Linea marcata + area colorata sotto, cosi' la salita/discesa si vede
    bene anche su schermo piccolo e con variazioni minime.
    """
    storico_punti = [p for p in storico_punti if p["saldo"] == p["saldo"]]  # scarta eventuali NaN (un NaN non e' mai uguale a se stesso)
    if len(storico_punti) < 2:
        return '<p class="muto" style="margin-top:8px;">Non ci sono ancora abbastanza dati per un grafico.</p>'

    valori = [p["saldo"] for p in storico_punti]
    larghezza, altezza = 340, 70
    minimo, massimo = min(valori), max(valori)
    intervallo = (massimo - minimo) or 1.0

    coordinate = []
    for i, v in enumerate(valori):
        x = (i / (len(valori) - 1)) * larghezza
        y = altezza - ((v - minimo) / intervallo) * (altezza - 20) - 10
        coordinate.append((x, y))

    polilinea = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinate)
    punti_area = f"0,{altezza} " + polilinea + f" {larghezza:.1f},{altezza}"
    puntini = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{colore}"/>' for x, y in coordinate
    )

    return (
        f'<svg viewBox="0 0 {larghezza} {altezza}" width="100%" height="{altezza}" '
        f'preserveAspectRatio="none" style="margin-top: 10px; overflow: visible;">'
        f'<polygon points="{punti_area}" fill="{colore}" opacity="0.12"/>'
        f'<polyline points="{polilinea}" fill="none" stroke="{colore}" stroke-width="3" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'{puntini}'
        f'</svg>'
    )


CSS = """
  body { font-family: -apple-system, system-ui, sans-serif; background: #f4f5f4; margin: 0; padding: 1.5rem 1rem; color: #1a1a1a; }
  .card { max-width: 400px; margin: 0 auto 1rem; background: #ffffff; border-radius: 14px; border: 1px solid #e4e4e4; padding: 1.25rem; }
  h1 { font-size: 1.1rem; margin: 0 0 1rem; display: flex; align-items: center; }
  h1 svg { margin-right: 8px; }
  h2 { font-size: 0.78rem; color: #888; margin: 0 0 8px; text-transform: uppercase; letter-spacing: .03em; }
  .saldo { text-align: center; margin-bottom: 1rem; }
  .saldo .valore { font-size: 2.1rem; font-weight: 600; margin: 0; }
  .saldo .etichetta { font-size: 0.8rem; color: #666; margin: 0 0 4px; }
  .saldo .oggi { font-size: 0.8rem; margin: 4px 0 8px; }
  .badge svg { margin-right: 5px; }
  .badge { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 500; }
  .badge.verde { background: #e3f5e9; color: #1e7d3c; }
  .badge.ambra { background: #fdf1dd; color: #9a6a11; }
  .badge.grigio { background: #eee; color: #555; }
  .riga { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; }
  .riga:last-child { border-bottom: none; }
  .destra { display: flex; align-items: center; }
  .destra > * + * { margin-left: 8px; }
  .destra-col { display: flex; flex-direction: column; align-items: flex-end; }
  .elenco-punti { margin-top: 4px; }
  .elenco-punti .riga { font-size: 0.8rem; color: #666; padding: 5px 0; }
  .delta { font-size: 0.75rem; min-width: 48px; text-align: right; }
  .su { color: #1e7d3c; } .giu { color: #c9432b; } .neutro { color: #999; }
  .muto { color: #999; font-size: 0.85rem; }
  .tag { font-size: 0.68rem; padding: 2px 8px; border-radius: 999px; margin-left: 7px; }
  .tag-etf { background: #eef2ff; color: #4f5fd6; }
  .tag-crypto { background: #fdeeee; color: #c9432b; }
  .tag-azione { background: #fdf1dd; color: #9a6a11; }
  .var { font-size: 0.75rem; }
  .barra-sfondo { background: #eee; border-radius: 999px; height: 7px; overflow: hidden; margin-top: 6px; }
  .barra-riempita { background: #c9432b; height: 100%; border-radius: 999px; }
  .controllo .quando { margin-right: 12px; }
  .controllo { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.8rem; }
  .controllo:last-child { border-bottom: none; }
  .controllo .quando { color: #555; white-space: nowrap; }
  .controllo .esito { text-align: right; }
  .controllo .ok { color: #1e7d3c; } .controllo .avviso { color: #9a6a11; }
  .notifica { background: #f7f7f7; border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; font-size: 0.85rem; }
  .notifica.conferma { background: #fdf1dd; }
  .notifica .data { color: #999; font-size: 0.75rem; }
  .bottoni { display: flex; margin-top: 10px; }
  .bottoni .bottone + .bottone { margin-left: 8px; }
  .bottone { flex: 1; text-align: center; padding: 8px; border-radius: 8px; font-size: 0.85rem; font-weight: 500; text-decoration: none; }
  .bottone.primario { background: #1e7d3c; color: #fff; }
  .bottone.secondario { background: #eee; color: #444; }
  .bottone.disabilitato { flex: none; padding: 6px 12px; font-size: 0.78rem; background: #f0f0f0; color: #aaa; }
  .impostazioni .riga { font-size: 0.82rem; padding: 6px 0; }
  .impostazioni .riga span:last-child { font-weight: 500; }
"""


def _delta_html(delta: float) -> str:
    if abs(delta) < 0.005:
        return '<span class="delta neutro">0.00€</span>'
    classe, segno = ("su", "+") if delta > 0 else ("giu", "-")
    return f'<span class="delta {classe}">{segno}{abs(delta):.2f}€</span>'


def _punti_validi(storico_punti: list[dict]) -> list[dict]:
    """Scarta eventuali punti con saldo non valido (NaN: un NaN non e' mai uguale a se stesso)."""
    return [p for p in storico_punti if p["saldo"] == p["saldo"]]


def _elenco_punti(storico_punti: list[dict]) -> str:
    """
    Cronologia compatta, dal giorno piu' recente: data, saldo e variazione in euro
    rispetto al giorno prima (verde/rosso). Un piccolo simbolo compare SOLO nei
    giorni in cui e' successo qualcosa di rilevante (stop-loss, take-profit, cambio, nuova apertura).
    """
    punti = _punti_validi(storico_punti)
    if not punti:
        return ""
    righe = []
    for i, p in enumerate(punti):
        delta = _delta_html(p["saldo"] - punti[i - 1]["saldo"]) if i > 0 else '<span class="delta"></span>'
        icona = _icona("evento") + " " if p.get("evento") else ""
        righe.append(
            f'<div class="riga"><span>{icona}{escape(p["data_ora"])}</span>'
            f'<span class="destra"><span>{p["saldo"]:.2f} €</span>{delta}</span></div>'
        )
    return f'<div class="elenco-punti">{"".join(reversed(righe))}</div>'


def _riga_oggi(storico_punti: list[dict], giorno_contatore: str, controlli_oggi: int) -> str:
    """'+0.25€ oggi · 2/4 controlli': variazione rispetto a ieri + quanti cicli sono girati oggi."""
    oggi = datetime.now().strftime("%d/%m")
    parti = []
    punti = _punti_validi(storico_punti)
    if len(punti) >= 2 and punti[-1]["data_ora"].split(" ")[0] == oggi:
        delta = punti[-1]["saldo"] - punti[-2]["saldo"]
        classe = "neutro" if abs(delta) < 0.005 else ("su" if delta > 0 else "giu")
        segno = "" if abs(delta) < 0.005 else ("+" if delta > 0 else "-")
        parti.append(f'<span class="{classe}" style="font-weight:500;">{segno}{abs(delta):.2f}€ oggi</span>')
    fatti = controlli_oggi if giorno_contatore == oggi else 0
    parti.append(f'<span class="muto">{fatti}/{config.CONTROLLI_GIORNALIERI_ATTESI} controlli</span>')
    return " · ".join(parti)


def _badge_trend(direzione: str) -> str:
    if direzione == "crescita":
        return f'<span class="badge verde">{_icona("su", "#1e7d3c")} In crescita</span>'
    if direzione == "calo":
        return f'<span class="badge ambra">{_icona("giu", "#9a6a11")} In calo</span>'
    return f'<span class="badge grigio">{_icona("pari", "#555")} Stabile</span>'


def _valore_posizione(p) -> float:
    return p.quota_investita * (1 + p.ultima_variazione_pct)


def _posizioni_html(posizioni: dict) -> str:
    """Una riga per posizione: ticker + etichetta di categoria, valore, variazione colorata."""
    if not posizioni:
        return '<p class="muto">Nessuna posizione aperta al momento.</p>'
    righe = []
    for ticker, p in posizioni.items():
        etichetta = config.etichetta_di(ticker)
        classe_tag = {"ETF": "tag-etf", "Crypto": "tag-crypto"}.get(etichetta, "tag-azione")
        pct = p.ultima_variazione_pct * 100
        classe_var = "neutro" if abs(pct) < 0.05 else ("su" if pct > 0 else "giu")
        righe.append(
            f'<div class="riga"><span>{escape(ticker)}<span class="tag {classe_tag}">{etichetta}</span></span>'
            f'<span class="destra-col"><span>{_valore_posizione(p):.2f} €</span>'
            f'<span class="var {classe_var}">{pct:+.1f}%</span></span></div>'
        )
    return "".join(righe)


def _rischio_html(posizioni: dict, saldo: float) -> str:
    """Quanto del tetto massimo su crypto/azioni e' gia' impegnato (barra piena = tetto raggiunto)."""
    valore = sum(_valore_posizione(p) for t, p in posizioni.items() if config.categoria_di(t) == "rischioso")
    tetto = config.TETTO_RISCHIOSO_PCT * saldo
    percentuale = min(100.0, valore / tetto * 100) if tetto > 0 else 0.0
    return (
        f'<div class="riga" style="border-bottom:none; padding-bottom:0;">'
        f'<span>{valore:.2f} € impegnati</span>'
        f'<span class="muto">tetto {config.TETTO_RISCHIOSO_PCT:.0%} ({tetto:.2f} €)</span></div>'
        f'<div class="barra-sfondo"><div class="barra-riempita" style="width:{percentuale:.0f}%"></div></div>'
    )


def _controlli_html(storico_controlli: list[dict]) -> str:
    """Ultimi controlli del ciclo di sicurezza (finestra a scorrimento), dal piu' recente."""
    if not storico_controlli:
        return '<p class="muto">Nessun controllo ancora eseguito.</p>'
    ok = "Nessuna variazione critica."
    return "".join(
        f'<div class="controllo"><span class="quando">{escape(c["data_ora"])}</span>'
        f'<span class="esito {"ok" if c["esito"] == ok else "avviso"}">{escape(c["esito"])}</span></div>'
        for c in reversed(storico_controlli)
    )


def _funzione_bloccata(titolo: str, tipo_notifica_attiva: bool) -> str:
    """
    Indicazione semplice che una funzione (salvadanaio, nuova posizione) esiste
    ma non e' ancora disponibile - nessun numero o barra di avanzamento, solo un
    bottone grigio. Se esiste gia' una notifica vera attiva per questo tipo, non
    la mostriamo (la notifica vera con i bottoni attivi la sostituisce).
    """
    if tipo_notifica_attiva:
        return ""
    return (
        f'<div class="riga"><span>{titolo}</span>'
        f'<span class="bottone disabilitato">Non ancora disponibile</span></div>'
    )


def genera() -> None:
    CARTELLA_OUTPUT.mkdir(exist_ok=True)

    stato_e_portafoglio = state_store.carica_stato()
    impostazioni = settings_store.carica_impostazioni()
    notifiche_non_lette = notifications.non_lette()

    if stato_e_portafoglio is None:
        saldo, salvadanaio, direzione, posizioni = 0.0, 0.0, "stabile", {}
        storico_punti, storico_controlli, giorno_contatore, controlli_oggi = [], [], "", 0
    else:
        stato, portafoglio = stato_e_portafoglio
        saldo = portafoglio.saldo_investito
        salvadanaio = portafoglio.salvadanaio
        direzione, _ = portafoglio.giorni_di_trend()
        posizioni = stato.posizioni
        storico_punti = portafoglio.storico_punti
        storico_controlli = portafoglio.storico_controlli_sicurezza
        giorno_contatore = portafoglio.giorno_contatore_controlli
        controlli_oggi = portafoglio.controlli_oggi

    colore_grafico = "#c9432b" if direzione == "calo" else "#1e7d3c"

    righe_notifiche = "".join(
        f'<div class="notifica {"conferma" if n["richiede_conferma"] else ""}">'
        f'<p>{n["messaggio"]}</p><span class="data">{n["data"]}</span>'
        f'{_bottoni_per_notifica(n)}'
        f'</div>'
        for n in notifiche_non_lette
    ) or '<p class="muto">Nessuna notifica in sospeso.</p>'

    tipi_attivi = {n["tipo"] for n in notifiche_non_lette}
    posizioni_consentite = impostazioni["POSIZIONI_CONSENTITE"]
    ce_altra_soglia = (posizioni_consentite - 1) < len(config.SOGLIE_POSIZIONI_AGGIUNTIVE)
    funzioni_bloccate = (
        _funzione_bloccata("Salvadanaio", "salvadanaio" in tipi_attivi)
        + (_funzione_bloccata("Nuova posizione", "nuova_posizione" in tipi_attivi) if ce_altra_soglia else "")
    )
    blocco_prossimi_passi = (
        f'<div class="card"><h2>Prossimi passi</h2>{funzioni_bloccate}</div>' if funzioni_bloccate else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Salvabot</title>
<style>{CSS}</style>
</head>
<body>

  <div class="card">
    <h1>{_icona('salvadanaio', '#1e7d3c')} Salvabot</h1>
    <div class="saldo">
      <p class="etichetta">Saldo investito</p>
      <p class="valore">{saldo:.2f} €</p>
      <p class="oggi">{_riga_oggi(storico_punti, giorno_contatore, controlli_oggi)}</p>
      {_badge_trend(direzione)}
    </div>
    {_sparkline(storico_punti, colore_grafico)}
    {_elenco_punti(storico_punti)}
    <div class="riga" style="margin-top: 10px;"><span>Salvadanaio</span><span>{salvadanaio:.2f} €</span></div>
  </div>

  <div class="card">
    <h2>Posizioni aperte</h2>
    {_posizioni_html(posizioni)}
  </div>

  <div class="card">
    <h2>Rischio crypto/azioni</h2>
    {_rischio_html(posizioni, saldo)}
  </div>

  <div class="card">
    <h2>Ultimi controlli di sicurezza</h2>
    {_controlli_html(storico_controlli)}
  </div>

  <div class="card">
    <h2>Notifiche</h2>
    {righe_notifiche}
  </div>

  {blocco_prossimi_passi}

  <div class="card impostazioni">
    <h2>Impostazioni attuali</h2>
    <div class="riga"><span>Cautela</span><span>{impostazioni['CAUTELA']}</span></div>
    <div class="riga"><span>Stop-loss ETF</span><span>{impostazioni['STOP_LOSS_PCT']:.0%}</span></div>
    <div class="riga"><span>Take-profit ETF</span><span>{impostazioni['TAKE_PROFIT_PCT']:.0%}</span></div>
    <div class="riga"><span>Stop-loss crypto/azioni</span><span>{config.STOP_LOSS_PCT_RISCHIOSO:.0%}</span></div>
    <div class="riga"><span>Take-profit crypto/azioni</span><span>{config.TAKE_PROFIT_PCT_RISCHIOSO:.0%}</span></div>
    <div class="riga"><span>Tetto crypto/azioni</span><span>{config.TETTO_RISCHIOSO_PCT:.0%}</span></div>
    <div class="riga"><span>Posizioni consentite</span><span>{posizioni_consentite}</span></div>
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

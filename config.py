"""
Configurazione di Salvabot.

Tutti i numeri "prudenti" discussi nel progetto vivono qui, come parametri
modificabili — nessuno di questi valori è definitivo, sono un punto di
partenza ragionevole da affinare osservando i risultati della demo.
"""

# --- Capitale iniziale (impostabile dall'utente in fase di setup) ---
SALDO_INIZIALE_DEFAULT = 30.0

# --- Gestione del rischio per gli ETF ---
STOP_LOSS_PCT = -0.10          # vende se un ETF scende del 10% dal prezzo di carico
TAKE_PROFIT_PCT = 0.15         # consolida se un ETF sale del 15% dal prezzo di carico

# --- Gestione del rischio per crypto/azioni (più ampia: si muovono di più) ---
STOP_LOSS_PCT_RISCHIOSO = -0.20
TAKE_PROFIT_PCT_RISCHIOSO = 0.30

# --- Soglia di volatilità nello scoring, diversa per categoria ---
# (la volatilità tipica di crypto/azioni è naturalmente più alta di un ETF,
# quindi servono soglie diverse perché possano mai risultare "convincenti")
SOGLIA_VOLATILITA_ETF = 0.20
SOGLIA_VOLATILITA_RISCHIOSO = 0.80

# --- Livello di cautela: quanti indicatori su 3 devono essere allineati
#     prima che Salvabot decida di investire invece di aspettare ---
LIVELLI_CAUTELA = {
    "prudente": 3,     # tutti e 3 gli indicatori devono essere favorevoli
    "equilibrato": 2,  # almeno 2 su 3
    "dinamico": 1,     # basta 1 su 3
}
CAUTELA_DEFAULT = "equilibrato"

# --- Frequenza operativa ---
GIORNI_TRA_UNA_DECISIONE_E_LALTRA = 7  # analisi giornaliera, ma decisioni operative al massimo settimanali

# --- Modalità difensiva su crollo di mercato generalizzato ---
CRASH_SOGLIA_PCT = -0.15       # se l'indice di riferimento scende oltre il 15%...
CRASH_FINESTRA_GIORNI = 30     # ...in questo numero di giorni
CRASH_GIORNI_DI_RAFFREDDAMENTO = 14  # Salvabot non ricompra per questo periodo dopo un crash rilevato

# --- Paniere di ETF, a scalini in base al saldo (nessun numero fisso) ---
# Ogni voce: (saldo minimo, lista ticker). yfinance-style ticker.
PANIERE_PER_FASCIA_DI_SALDO = [
    (0,    ["VWCE.DE", "EUNA.DE"]),                              # 2 ETF: azionario globale + obbligazionario
    (100,  ["VWCE.DE", "EUNA.DE", "MEUD.PA"]),                   # + azionario Europa
    (300,  ["VWCE.DE", "EUNA.DE", "MEUD.PA", "IS3N.DE"]),        # + mercati emergenti
]

# --- Soglia di "maturità" del saldo per il salvadanaio (non tempo fisso) ---
SOGLIA_PROPOSTA_SALVADANAIO = 300.0   # da qui in poi può proporre di mettere via una parte

# --- Crypto e azioni: disponibili da subito, nessuna soglia (deciso nel progetto) ---
# Rivedere periodicamente questa lista insieme all'utente in base a come si muove il mercato.
PANIERE_RISCHIOSO = ["BTC-USD", "ETH-USD", "AAPL", "MSFT", "GOOGL", "AMZN"]

# Categoria di ogni ticker: 'etf' o 'rischioso' (crypto/azione). Usata per scegliere
# le soglie di stop-loss/take-profit/volatilità giuste e per il tetto di rischio.
def categoria_di(ticker: str) -> str:
    return "rischioso" if ticker in PANIERE_RISCHIOSO else "etf"

def etichetta_di(ticker: str) -> str:
    """Etichetta leggibile da mostrare sulla pagina: 'ETF', 'Crypto' o 'Azione'."""
    if categoria_di(ticker) == "etf":
        return "ETF"
    return "Crypto" if ticker.endswith("-USD") else "Azione"

# --- Tetto massimo su crypto/azioni insieme, rispetto al saldo totale ---
TETTO_RISCHIOSO_PCT = 0.50   # se raggiunto, Salvabot sceglie solo tra gli ETF rimasti
# Con UNA sola posizione in portafoglio, Salvabot investe tutto il capitale su quella:
# il tetto del 50% la renderebbe impossibile per crypto/azioni (100% > 50%).
# False = il tetto si applica solo quando c'e' gia' almeno un'altra posizione (come concordato).
# True  = il tetto vale sempre: finche' c'e' una sola posizione, Salvabot scegliera' solo ETF.
TETTO_ANCHE_CON_UNA_POSIZIONE = False

# --- Ciclo di sicurezza (solo su crypto/azioni): quanti controlli mostrare a scorrimento ---
FINESTRA_CONTROLLI_SICUREZZA = 4
CONTROLLI_GIORNALIERI_ATTESI = 4   # 3 di sicurezza + il ciclo principale serale (mostrato come "X/4")

# --- Repository GitHub (serve per generare i link di conferma nella pagina web) ---
# Sostituisci con "tuonomeutente/nomerepository" una volta creato il repository.
GITHUB_REPO = "GitAntonio78/salvabot"

# --- Cambio posizione se ne trova una migliore ---
COMMISSIONE_STIMATA_EUR = 2.5              # stima prudente per operazione (da affinare con i costi reali del broker)
SOGLIA_DIFFERENZA_CRITERI_SWITCH = 1       # il nuovo ETF deve avere almeno N criteri favorevoli in più

# --- Posizioni multiple: proposte a soglia (mai automatiche) ---
# Indice 0 = soglia per passare da 1 a 2 posizioni, indice 1 = da 2 a 3, ecc.
SOGLIE_POSIZIONI_AGGIUNTIVE = [150.0, 400.0]

# --- Criteri minimi di validazione demo prima di valutare il passaggio al reale ---
DEMO_SETTIMANE_MINIME = 8
DEMO_CICLI_MINIMI = 5

# --- Auto-valutazione: quando Salvabot propone di rivedere le sue impostazioni ---
VALUTAZIONE_FINESTRA_CICLI = 10        # analizza gli ultimi N cicli
VALUTAZIONE_CICLI_MINIMI = 5           # non valuta nulla prima di aver visto almeno N cicli
SOGLIA_TROPPI_STOP_LOSS = 3            # N stop-loss nella finestra = "troppo spesso"
SOGLIA_TROPPA_ATTESA_PCT = 0.85        # se aspetta piu' dell'85% delle volte, forse e' troppo cauto
SOGLIA_DRAWDOWN_PREOCCUPANTE_PCT = -0.12  # calo dal massimo storico del portafoglio

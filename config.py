"""
Configurazione di Salvabot.

Tutti i numeri "prudenti" discussi nel progetto vivono qui, come parametri
modificabili — nessuno di questi valori è definitivo, sono un punto di
partenza ragionevole da affinare osservando i risultati della demo.
"""

# --- Capitale iniziale (impostabile dall'utente in fase di setup) ---
SALDO_INIZIALE_DEFAULT = 30.0

# --- Gestione del rischio (le uniche due regole, come deciso nel progetto) ---
STOP_LOSS_PCT = -0.10          # vende se un ETF scende del 10% dal prezzo di carico
TAKE_PROFIT_PCT = 0.15         # consolida se un ETF sale del 15% dal prezzo di carico

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
    (0,    ["VWCE.DE", "AGGH.DE"]),                              # 2 ETF: azionario globale + obbligazionario
    (100,  ["VWCE.DE", "AGGH.DE", "MEUD.PA"]),                   # + azionario Europa
    (300,  ["VWCE.DE", "AGGH.DE", "MEUD.PA", "IS3N.DE"]),        # + mercati emergenti
]

# --- Soglie di "maturità" del saldo (non tempo fisso) ---
# Sopra queste soglie, Salvabot PUO' proporre (mai imporre) un passo successivo.
SOGLIA_PROPOSTA_SALVADANAIO = 300.0   # da qui in poi può proporre di mettere via una parte
SOGLIA_PROPOSTA_ESPANSIONE = 300.0    # da qui in poi può proporre di provare crypto/azioni

# --- Repository GitHub (serve per generare i link di conferma nella pagina web) ---
# Sostituisci con "tuonomeutente/nomerepository" una volta creato il repository.
GITHUB_REPO = "tuonomeutente/salvabot"

# --- Criteri minimi di validazione demo prima di valutare il passaggio al reale ---
DEMO_SETTIMANE_MINIME = 8
DEMO_CICLI_MINIMI = 5

# --- Auto-valutazione: quando Salvabot propone di rivedere le sue impostazioni ---
VALUTAZIONE_FINESTRA_CICLI = 10        # analizza gli ultimi N cicli
VALUTAZIONE_CICLI_MINIMI = 5           # non valuta nulla prima di aver visto almeno N cicli
SOGLIA_TROPPI_STOP_LOSS = 3            # N stop-loss nella finestra = "troppo spesso"
SOGLIA_TROPPA_ATTESA_PCT = 0.85        # se aspetta piu' dell'85% delle volte, forse e' troppo cauto
SOGLIA_DRAWDOWN_PREOCCUPANTE_PCT = -0.12  # calo dal massimo storico del portafoglio

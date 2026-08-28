"""
Esegue UN SOLO ciclo operativo di Salvabot con dati aggiornati ad oggi:
1. Carica lo stato salvato (o ne crea uno nuovo al primo avvio)
2. Scarica i dati di mercato più recenti
3. Prende le decisioni del ciclo (investi/aspetta/vendi)
4. Salva lo stato aggiornato
5. Stampa un log leggibile

Questo e' il file che, quando avremo il server, verra' lanciato in automatico
ogni giorno (es. con un cron job) — a differenza di simulator.py, che serve
solo per testare la strategia su dati storici, non per l'uso reale.
"""

import argparse
from pathlib import Path

import pandas as pd

import config
import data_provider
import decision_engine
import notifications
import self_evaluation
import settings_store
import state_store
from portfolio import Portafoglio


def esegui_singolo_ciclo(
    saldo_iniziale: float = config.SALDO_INIZIALE_DEFAULT,
    cautela: str | None = None,
    percorso_stato: Path = state_store.FILE_STATO_DEFAULT,
    ticker_indice_riferimento: str = "VWCE.DE",
) -> dict:
    impostazioni = settings_store.carica_impostazioni()
    settings_store.applica_a_config(impostazioni)
    if cautela is None:
        cautela = impostazioni["CAUTELA"]

    stato_precedente = state_store.carica_stato(percorso_stato)

    primo_avvio = stato_precedente is None
    if primo_avvio:
        stato = decision_engine.StatoBot(saldo_disponibile=saldo_iniziale)
        portafoglio = Portafoglio(saldo_investito=saldo_iniziale)
    else:
        stato, portafoglio = stato_precedente

    tutti_i_ticker = sorted({t for _, lista in config.PANIERE_PER_FASCIA_DI_SALDO for t in lista})
    dati_per_ticker = data_provider.scarica_paniere(tutti_i_ticker, giorni=400)

    serie_indice = dati_per_ticker[ticker_indice_riferimento]["Close"]
    if isinstance(serie_indice, pd.DataFrame):
        serie_indice = serie_indice.iloc[:, 0]

    oggi = serie_indice.index[-1]

    log = decision_engine.decidi_ciclo(
        stato=stato,
        dati_per_ticker=dati_per_ticker,
        prezzi_indice_riferimento=serie_indice,
        oggi=oggi,
        cautela=cautela,
        posizioni_consentite=impostazioni["POSIZIONI_CONSENTITE"],
    )

    valore_posizioni = decision_engine._valore_posizioni(stato, dati_per_ticker, oggi)
    saldo_operativo = stato.saldo_disponibile + valore_posizioni
    portafoglio.saldo_investito = saldo_operativo
    portafoglio.registra_saldo_giornaliero(saldo_operativo)

    eventi = []
    for evento in log:
        portafoglio.registra_evento(str(oggi.date()), evento["tipo"])
        eventi.append(evento["messaggio"])
        if evento["tipo"] == "difensiva" and "Rilevato calo" in evento["messaggio"]:
            notifications.invia("crash", evento["messaggio"], str(oggi.date()), richiede_conferma=False)

    if primo_avvio:
        eventi.insert(0, f"Primo avvio: Salvabot parte con un saldo di {saldo_iniziale:.2f} EUR.")

    if portafoglio.puo_proporre_salvadanaio():
        msg = (
            f"Saldo adeguato ({saldo_operativo:.2f} EUR): "
            f"vuoi mettere via una parte nel salvadanaio?"
        )
        notifications.invia("salvadanaio", msg, str(oggi.date()), richiede_conferma=True)
        eventi.append(f"[proposta] {msg}")

    if portafoglio.puo_proporre_espansione():
        msg = (
            f"Saldo adeguato ({saldo_operativo:.2f} EUR): "
            f"vuoi che provi anche crypto o azioni con una piccola quota?"
        )
        notifications.invia("espansione", msg, str(oggi.date()), richiede_conferma=True)
        eventi.append(f"[proposta] {msg}")

    if portafoglio.puo_proporre_nuova_posizione(impostazioni["POSIZIONI_CONSENTITE"]):
        prossimo_numero = impostazioni["POSIZIONI_CONSENTITE"] + 1
        msg = (
            f"Saldo adeguato ({saldo_operativo:.2f} EUR) per diversificare: "
            f"vuoi che provi ad aprire una {prossimo_numero}a posizione insieme a quella attuale?"
        )
        notifications.invia("nuova_posizione", msg, str(oggi.date()), richiede_conferma=True)
        eventi.append(f"[proposta] {msg}")

    proposte_autovalutazione = self_evaluation.valuta(portafoglio, cautela_attuale=cautela)
    for p in proposte_autovalutazione:
        msg = f"{p.problema} Propongo: {p.proposta}."
        notifications.invia("autovalutazione", msg, str(oggi.date()), richiede_conferma=True)
        eventi.append(f"[auto-valutazione] {msg}")

    state_store.salva_stato(stato, portafoglio, percorso_stato)

    direzione, giorni_trend = portafoglio.giorni_di_trend()

    return {
        "eventi": eventi,
        "proposte_autovalutazione": proposte_autovalutazione,
        "saldo_investito": round(portafoglio.saldo_investito, 2),
        "salvadanaio": round(portafoglio.salvadanaio, 2),
        "trend": direzione,
        "giorni_di_trend": giorni_trend,
        "data_ciclo": str(oggi.date()),
        "dati_reali_usati": data_provider.YFINANCE_DISPONIBILE,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Esegue un singolo ciclo operativo di Salvabot")
    parser.add_argument("--saldo", type=float, default=config.SALDO_INIZIALE_DEFAULT)
    parser.add_argument("--cautela", choices=list(config.LIVELLI_CAUTELA.keys()), default=config.CAUTELA_DEFAULT)
    parser.add_argument("--stato", type=str, default=str(state_store.FILE_STATO_DEFAULT))
    args = parser.parse_args()

    risultato = esegui_singolo_ciclo(
        saldo_iniziale=args.saldo, cautela=args.cautela, percorso_stato=Path(args.stato)
    )

    print(f"\n--- Ciclo del {risultato['data_ciclo']} "
          f"(dati {'reali' if risultato['dati_reali_usati'] else 'sintetici'}) ---")
    for evento in risultato["eventi"]:
        print(f"- {evento}")
    print(f"\nSaldo investito: {risultato['saldo_investito']:.2f} EUR")
    print(f"Salvadanaio:     {risultato['salvadanaio']:.2f} EUR")
    print(f"Trend:           {risultato['trend']} da {risultato['giorni_di_trend']} cicli")

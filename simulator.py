"""
Simulatore demo: fa girare Salvabot su una serie storica di prezzi,
un ciclo alla volta, cosi' puoi vedere l'intero comportamento del bot
(inclusi stop-loss, attese, modalita' difensiva) prima di collegarlo
a soldi veri.
"""

import pandas as pd

import config
import data_provider
import decision_engine
import self_evaluation
from portfolio import Portafoglio


def esegui_demo(
    saldo_iniziale: float = config.SALDO_INIZIALE_DEFAULT,
    cautela: str = config.CAUTELA_DEFAULT,
    giorni_storico: int = 400,
    ticker_indice_riferimento: str = "VWCE.DE",
) -> dict:
    """Esegue una simulazione completa e restituisce log + metriche."""

    # Scarica dati per il paniere più ampio possibile (poi si filtra per fascia di saldo a ogni ciclo)
    tutti_i_ticker = sorted({t for _, lista in config.PANIERE_PER_FASCIA_DI_SALDO for t in lista})
    dati_per_ticker = data_provider.scarica_paniere(tutti_i_ticker, giorni=giorni_storico)

    serie_indice = dati_per_ticker[ticker_indice_riferimento]["Close"]
    if isinstance(serie_indice, pd.DataFrame):
        serie_indice = serie_indice.iloc[:, 0]

    stato = decision_engine.StatoBot(saldo_disponibile=saldo_iniziale)
    portafoglio = Portafoglio(saldo_investito=saldo_iniziale)

    log_completo = []
    date_cicli = serie_indice.index[::config.GIORNI_TRA_UNA_DECISIONE_E_LALTRA]

    for oggi in date_cicli:
        log_ciclo = decision_engine.decidi_ciclo(
            stato=stato,
            dati_per_ticker=dati_per_ticker,
            prezzi_indice_riferimento=serie_indice[serie_indice.index <= oggi],
            oggi=oggi,
            cautela=cautela,
        )

        valore_posizioni = decision_engine._valore_posizioni(stato, dati_per_ticker, oggi)
        saldo_operativo = stato.saldo_disponibile + valore_posizioni
        portafoglio.saldo_investito = saldo_operativo
        portafoglio.registra_saldo_giornaliero(saldo_operativo)

        for evento in log_ciclo:
            portafoglio.registra_evento(str(oggi.date()), evento["tipo"])
            log_completo.append(f"[{oggi.date()}] {evento['messaggio']}")

        # Proposte (qui simulate come semplice segnalazione nel log, non azioni automatiche)
        if portafoglio.puo_proporre_salvadanaio():
            log_completo.append(
                f"[{oggi.date()}] Saldo adeguato ({saldo_operativo:.2f} EUR): "
                f"Salvabot potrebbe proporre di mettere via una parte nel salvadanaio."
            )

    proposte_autovalutazione = self_evaluation.valuta(portafoglio, cautela_attuale=cautela)
    for p in proposte_autovalutazione:
        log_completo.append(f"[auto-valutazione] {p.problema} Propongo: {p.proposta}.")

    direzione, giorni_trend = portafoglio.giorni_di_trend()
    rendimento_pct = (portafoglio.saldo_investito - saldo_iniziale) / saldo_iniziale

    metriche = {
        "saldo_iniziale": saldo_iniziale,
        "saldo_finale": round(portafoglio.saldo_investito, 2),
        "rendimento_pct": round(rendimento_pct * 100, 2),
        "trend_attuale": direzione,
        "giorni_di_trend": giorni_trend,
        "cicli_totali": len(date_cicli),
        "dati_reali_usati": data_provider.YFINANCE_DISPONIBILE,
        "proposte_autovalutazione": len(proposte_autovalutazione),
    }

    return {"log": log_completo, "metriche": metriche}


if __name__ == "__main__":
    risultato = esegui_demo()

    print("=== LOG DELLA DEMO ===")
    for riga in risultato["log"]:
        print(riga)

    print("\n=== RISULTATO FINALE ===")
    for chiave, valore in risultato["metriche"].items():
        print(f"{chiave}: {valore}")

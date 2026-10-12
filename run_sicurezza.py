"""
Ciclo di SICUREZZA di Salvabot: gira più volte al giorno (a differenza del
ciclo principale, una volta sola) e si occupa SOLO delle posizioni crypto/
azioni, le più volatili:
- controlla stop-loss/take-profit (soglie dedicate, più ampie di quelle ETF)
- valuta un cambio-posizione se conviene (stesso controllo commissioni)

NON apre mai nuove posizioni da capitale libero (resta compito esclusivo
del ciclo principale) e NON gestisce salvadanaio/nuove posizioni/auto-
valutazione: questo script fa solo protezione, nient'altro.

Se Salvabot non è mai partito (nessuno stato salvato), questo script non
fa nulla: serve prima un primo avvio del ciclo principale (run_ciclo.py).
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

import config
import data_provider
import decision_engine
import settings_store
import state_store


def esegui_controllo_sicurezza(
    percorso_stato: Path = state_store.FILE_STATO_DEFAULT,
    ticker_riferimento: str = "BTC-USD",  # tratta tutti i giorni, utile come riferimento sempre fresco
) -> dict:
    stato_e_portafoglio = state_store.carica_stato(percorso_stato)
    if stato_e_portafoglio is None:
        return {
            "eseguito": False,
            "messaggio": "Nessuno stato trovato: serve prima un avvio del ciclo principale.",
        }

    stato, portafoglio = stato_e_portafoglio
    impostazioni = settings_store.carica_impostazioni()
    cautela = impostazioni["CAUTELA"]

    # Scarica lo stesso universo di ticker del ciclo principale: servono anche
    # i prezzi degli ETF eventualmente in portafoglio per calcolare il saldo totale.
    tutti_i_ticker = sorted(
        {t for _, lista in config.PANIERE_PER_FASCIA_DI_SALDO for t in lista} | set(config.PANIERE_RISCHIOSO)
    )
    dati_per_ticker = data_provider.scarica_paniere(tutti_i_ticker, giorni=400)

    serie_riferimento = dati_per_ticker[ticker_riferimento]["Close"]
    if isinstance(serie_riferimento, pd.DataFrame):
        serie_riferimento = serie_riferimento.iloc[:, 0]
    oggi = serie_riferimento.index[-1]

    # 1. Stop-loss/take-profit: sempre attivo, protegge a prescindere da tutto
    eventi = decision_engine.controlla_stop_loss_take_profit(
        stato, dati_per_ticker, oggi, solo_categoria="rischioso"
    )

    # 2. Cambio posizione, solo se non siamo in modalità difensiva (decisa dal ciclo principale)
    in_raffreddamento = (
        stato.in_raffreddamento_fino_al is not None and oggi < stato.in_raffreddamento_fino_al
    )
    if not in_raffreddamento:
        eventi.extend(
            decision_engine.valuta_switch(stato, dati_per_ticker, oggi, cautela, solo_categoria="rischioso")
        )

    for evento in eventi:
        portafoglio.registra_evento(str(oggi.date()), evento["tipo"])

    # Esito leggibile per la cronologia "ultimi controlli" sulla pagina
    eventi_rilevanti = [e["messaggio"] for e in eventi if e["tipo"] in ("stop_loss", "take_profit", "switch")]
    esito = " | ".join(eventi_rilevanti) if eventi_rilevanti else "Nessuna variazione critica."

    valore_posizioni = decision_engine._valore_posizioni(stato, dati_per_ticker, oggi)
    saldo_operativo = stato.saldo_disponibile + valore_posizioni
    if pd.isna(saldo_operativo):
        saldo_operativo = portafoglio.saldo_investito

    portafoglio.saldo_investito = saldo_operativo
    decision_engine.aggiorna_variazioni_posizioni(stato, dati_per_ticker, oggi)
    portafoglio.registra_saldo_giornaliero(saldo_operativo)

    adesso = datetime.now().strftime("%d/%m %H:%M")
    portafoglio.registra_punto(adesso, saldo_operativo, evento=bool(eventi_rilevanti))
    portafoglio.registra_controllo_giornata(datetime.now().strftime("%d/%m"))
    portafoglio.registra_controllo_sicurezza(adesso, esito)

    state_store.salva_stato(stato, portafoglio, percorso_stato)

    return {
        "eseguito": True,
        "data_ora": adesso,
        "esito": esito,
        "in_raffreddamento": in_raffreddamento,
        "saldo_investito": round(saldo_operativo, 2),
        "dati_reali_usati": data_provider.YFINANCE_DISPONIBILE,
    }


if __name__ == "__main__":
    risultato = esegui_controllo_sicurezza()

    if not risultato["eseguito"]:
        print(risultato["messaggio"])
    else:
        print(f"\n--- Controllo di sicurezza del {risultato['data_ora']} "
              f"(dati {'reali' if risultato['dati_reali_usati'] else 'sintetici'}) ---")
        print(f"Esito: {risultato['esito']}")
        if risultato["in_raffreddamento"]:
            print("(modalità difensiva attiva: nessun cambio valutato)")
        print(f"\nSaldo investito: {risultato['saldo_investito']:.2f} EUR")

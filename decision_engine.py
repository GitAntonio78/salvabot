"""
Motore decisionale di Salvabot.

Applica le regole di rischio decise nel progetto:
1. Pazienza in ingresso: investe solo se abbastanza convinto, altrimenti aspetta.
2. Stop-loss/take-profit in uscita: vende in automatico oltre soglia.
3. Cambio posizione se ne trova una nettamente migliore, ma SOLO se il
   guadagno gia' maturato copre le commissioni stimate del cambio.
4. Puo' tenere piu' posizioni insieme, ma solo fino al numero consentito
   (che sale solo con una conferma esplicita dell'utente, mai da solo).

Più la modalità difensiva per i crolli di mercato generalizzati.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
import scoring


@dataclass
class Posizione:
    ticker: str
    prezzo_di_carico: float
    quota_investita: float  # in euro


@dataclass
class StatoBot:
    saldo_disponibile: float
    posizioni: dict[str, Posizione] = field(default_factory=dict)
    in_raffreddamento_fino_al: pd.Timestamp | None = None


def rileva_crash(prezzi_indice: pd.Series) -> bool:
    """True se l'indice di riferimento è sceso oltre la soglia nella finestra configurata."""
    finestra = prezzi_indice.tail(config.CRASH_FINESTRA_GIORNI)
    if len(finestra) < 2:
        return False
    variazione = (finestra.iloc[-1] - finestra.iloc[0]) / finestra.iloc[0]
    return variazione <= config.CRASH_SOGLIA_PCT


def paniere_per_saldo(saldo: float) -> list[dict]:
    """Restituisce il paniere di ETF adatto alla fascia di saldo attuale."""
    paniere_scelto = config.PANIERE_PER_FASCIA_DI_SALDO[0][1]
    for soglia_minima, ticker_list in config.PANIERE_PER_FASCIA_DI_SALDO:
        if saldo >= soglia_minima:
            paniere_scelto = ticker_list
    return paniere_scelto


def valuta_switch(
    stato: StatoBot,
    dati_per_ticker: dict[str, pd.DataFrame],
    oggi: pd.Timestamp,
    cautela: str,
) -> list[dict]:
    """
    Per ogni posizione aperta, controlla se esiste un'alternativa nettamente
    migliore (almeno SOGLIA_DIFFERENZA_CRITERI_SWITCH criteri favorevoli in
    piu'). Cambia SOLO se il guadagno gia' maturato in euro sulla posizione
    attuale copre la stima delle commissioni del cambio (vendita + riacquisto).
    Altrimenti resta fermo, anche se l'alternativa sembra migliore.
    """
    eventi = []
    if not stato.posizioni:
        return eventi

    saldo_totale = stato.saldo_disponibile + _valore_posizioni(stato, dati_per_ticker, oggi)
    paniere_attuale = paniere_per_saldo(saldo_totale)
    dati_paniere = {t: dati_per_ticker[t] for t in paniere_attuale if t in dati_per_ticker}
    punteggi = scoring.valuta_paniere(dati_paniere)

    soglia_minima_criteri = config.LIVELLI_CAUTELA.get(cautela, 2)
    costo_stimato_switch = 2 * config.COMMISSIONE_STIMATA_EUR

    for ticker in list(stato.posizioni.keys()):
        posizione = stato.posizioni[ticker]
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            continue

        variazione = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico
        punteggio_attuale = punteggi.get(ticker, {}).get("criteri_favorevoli", 0)

        candidati_migliori = [
            (t, d) for t, d in punteggi.items()
            if t != ticker
            and t not in stato.posizioni
            and d["criteri_favorevoli"] >= soglia_minima_criteri
            and d["criteri_favorevoli"] >= punteggio_attuale + config.SOGLIA_DIFFERENZA_CRITERI_SWITCH
        ]
        if not candidati_migliori:
            continue

        candidati_migliori.sort(key=lambda c: (-c[1]["criteri_favorevoli"], c[1]["volatilita"]))
        nuovo_ticker, _ = candidati_migliori[0]

        guadagno_in_euro = posizione.quota_investita * variazione

        if variazione > 0 and guadagno_in_euro > costo_stimato_switch:
            valore_finale = posizione.quota_investita * (1 + variazione)
            stato.saldo_disponibile += valore_finale
            del stato.posizioni[ticker]
            eventi.append({
                "tipo": "switch",
                "messaggio": (
                    f"Trovata un'occasione migliore: chiuso {ticker} (+{variazione:.1%}, "
                    f"guadagno di {guadagno_in_euro:.2f} EUR copre le commissioni stimate) "
                    f"per lasciare spazio a {nuovo_ticker}."
                ),
            })
        else:
            eventi.append({
                "tipo": "attesa",
                "messaggio": (
                    f"{nuovo_ticker} sembra piu' promettente di {ticker}, ma il guadagno attuale "
                    f"non coprirebbe le commissioni stimate del cambio: resto fermo su {ticker}."
                ),
            })

    return eventi


def decidi_ciclo(
    stato: StatoBot,
    dati_per_ticker: dict[str, pd.DataFrame],
    prezzi_indice_riferimento: pd.Series,
    oggi: pd.Timestamp,
    cautela: str = config.CAUTELA_DEFAULT,
    posizioni_consentite: int = 1,
) -> list[dict]:
    """
    Esegue un ciclo decisionale completo. Modifica 'stato' sul posto e
    restituisce un elenco di messaggi/log leggibili sulle azioni compiute.
    """
    log = []

    # --- 0. Modalità difensiva: se siamo in raffreddamento dopo un crash, non si compra ---
    in_raffreddamento = (
        stato.in_raffreddamento_fino_al is not None and oggi < stato.in_raffreddamento_fino_al
    )

    if rileva_crash(prezzi_indice_riferimento):
        nuova_data_fine = oggi + pd.Timedelta(days=config.CRASH_GIORNI_DI_RAFFREDDAMENTO)
        if stato.in_raffreddamento_fino_al is None or nuova_data_fine > stato.in_raffreddamento_fino_al:
            stato.in_raffreddamento_fino_al = nuova_data_fine
            log.append({
                "tipo": "difensiva",
                "messaggio": (
                    f"Rilevato calo di mercato generalizzato: modalita' difensiva attiva fino al "
                    f"{nuova_data_fine.date()} (nessun nuovo acquisto in questo periodo)."
                ),
            })
        in_raffreddamento = True

    # --- 1. Gestione posizioni aperte: stop-loss / take-profit (sempre attivo) ---
    for ticker in list(stato.posizioni.keys()):
        posizione = stato.posizioni[ticker]
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            continue

        variazione = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico

        if variazione <= config.STOP_LOSS_PCT:
            valore_finale = posizione.quota_investita * (1 + variazione)
            stato.saldo_disponibile += valore_finale
            del stato.posizioni[ticker]
            log.append({
                "tipo": "stop_loss",
                "messaggio": (
                    f"Stop-loss su {ticker}: sceso del {variazione:.1%}, venduto. "
                    f"Nuovo saldo: {stato.saldo_disponibile:.2f} EUR."
                ),
            })
        elif variazione >= config.TAKE_PROFIT_PCT:
            valore_finale = posizione.quota_investita * (1 + variazione)
            stato.saldo_disponibile += valore_finale
            del stato.posizioni[ticker]
            log.append({
                "tipo": "take_profit",
                "messaggio": (
                    f"Guadagno consolidato su {ticker}: salito del {variazione:.1%}, venduto. "
                    f"Nuovo saldo: {stato.saldo_disponibile:.2f} EUR."
                ),
            })

    # --- 2. Se in raffreddamento, ci si ferma qui: nessun nuovo acquisto o cambio ---
    if in_raffreddamento:
        log.append({"tipo": "attesa", "messaggio": "In modalita' difensiva: nessun nuovo acquisto questo ciclo."})
        return log

    # --- 2b. Cambio posizione se ne trova una nettamente migliore (solo se conviene) ---
    log.extend(valuta_switch(stato, dati_per_ticker, oggi, cautela))

    # --- 3. Valutazione di nuove opportunita' (solo se c'e' saldo libero E spazio per una posizione in più) ---
    if stato.saldo_disponibile <= 0:
        return log
    if len(stato.posizioni) >= posizioni_consentite:
        return log

    paniere_attuale = paniere_per_saldo(stato.saldo_disponibile + _valore_posizioni(stato, dati_per_ticker, oggi))
    dati_paniere = {t: dati_per_ticker[t] for t in paniere_attuale if t in dati_per_ticker}
    punteggi = scoring.valuta_paniere(dati_paniere)

    soglia_minima_criteri = config.LIVELLI_CAUTELA.get(cautela, 2)

    # Scegli il miglior candidato non ancora in portafoglio
    candidati = [
        (ticker, dettagli)
        for ticker, dettagli in punteggi.items()
        if ticker not in stato.posizioni and dettagli["criteri_favorevoli"] >= soglia_minima_criteri
    ]

    if not candidati:
        log.append({"tipo": "attesa", "messaggio": "Nessuna condizione abbastanza convincente: Salvabot resta in osservazione."})
        return log

    # Il migliore è quello con più criteri favorevoli (a parità, volatilità più bassa)
    candidati.sort(key=lambda c: (-c[1]["criteri_favorevoli"], c[1]["volatilita"]))
    ticker_scelto, dettagli_scelto = candidati[0]

    prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker_scelto], oggi)
    if prezzo_attuale is None:
        return log

    quota_investita = stato.saldo_disponibile  # investe tutto il disponibile sull'occasione migliore
    stato.posizioni[ticker_scelto] = Posizione(
        ticker=ticker_scelto, prezzo_di_carico=prezzo_attuale, quota_investita=quota_investita
    )
    stato.saldo_disponibile = 0.0
    log.append({
        "tipo": "investito",
        "messaggio": (
            f"Investiti {quota_investita:.2f} EUR su {ticker_scelto} "
            f"({dettagli_scelto['criteri_favorevoli']}/3 criteri favorevoli)."
        ),
    })

    return log


def _ultimo_prezzo(df: pd.DataFrame, fino_a: pd.Timestamp) -> float | None:
    serie = df["Close"]
    if isinstance(serie, pd.DataFrame):
        serie = serie.iloc[:, 0]
    serie_filtrata = serie[serie.index <= fino_a]
    if serie_filtrata.empty:
        return None
    return float(serie_filtrata.iloc[-1])


def _valore_posizioni(stato: StatoBot, dati_per_ticker: dict[str, pd.DataFrame], oggi: pd.Timestamp) -> float:
    totale = 0.0
    for ticker, posizione in stato.posizioni.items():
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            totale += posizione.quota_investita
            continue
        variazione = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico
        totale += posizione.quota_investita * (1 + variazione)
    return totale

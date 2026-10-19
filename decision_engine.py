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
    ultima_variazione_pct: float = 0.0  # variazione dall'acquisto all'ultimo controllo (per la pagina)


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


def paniere_per_saldo(saldo: float) -> list[str]:
    """
    Restituisce il paniere completo adatto alla fascia di saldo attuale:
    gli ETF a scalini (come sempre) + crypto/azioni, disponibili da subito
    senza soglia (deciso nel progetto).
    """
    paniere_etf = config.PANIERE_PER_FASCIA_DI_SALDO[0][1]
    for soglia_minima, ticker_list in config.PANIERE_PER_FASCIA_DI_SALDO:
        if saldo >= soglia_minima:
            paniere_etf = ticker_list
    return paniere_etf + config.PANIERE_RISCHIOSO


def soglie_rischio(ticker: str) -> tuple[float, float]:
    """Restituisce (stop_loss_pct, take_profit_pct) giusti per la categoria del ticker."""
    if config.categoria_di(ticker) == "rischioso":
        return config.STOP_LOSS_PCT_RISCHIOSO, config.TAKE_PROFIT_PCT_RISCHIOSO
    return config.STOP_LOSS_PCT, config.TAKE_PROFIT_PCT


def valore_per_categoria(
    stato: StatoBot, dati_per_ticker: dict[str, pd.DataFrame], oggi: pd.Timestamp, categoria: str
) -> float:
    """Somma il valore attuale delle sole posizioni di una categoria ('etf' o 'rischioso')."""
    totale = 0.0
    for ticker, posizione in stato.posizioni.items():
        if config.categoria_di(ticker) != categoria:
            continue
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            totale += posizione.quota_investita
            continue
        variazione = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico
        totale += posizione.quota_investita * (1 + variazione)
    return totale


def controlla_stop_loss_take_profit(
    stato: StatoBot,
    dati_per_ticker: dict[str, pd.DataFrame],
    oggi: pd.Timestamp,
    solo_categoria: str | None = None,
) -> list[dict]:
    """
    Controlla ogni posizione aperta e vende se ha superato la soglia di
    stop-loss o take-profit GIUSTA PER LA SUA CATEGORIA (ETF o rischioso).
    Se 'solo_categoria' e' indicato, controlla solo le posizioni di quella
    categoria (usato dal ciclo di sicurezza, che si occupa solo di crypto/azioni).
    """
    log = []
    for ticker in list(stato.posizioni.keys()):
        if solo_categoria is not None and config.categoria_di(ticker) != solo_categoria:
            continue

        posizione = stato.posizioni[ticker]
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            continue

        variazione = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico
        stop_loss_pct, take_profit_pct = soglie_rischio(ticker)

        if variazione <= stop_loss_pct:
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
        elif variazione >= take_profit_pct:
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
    return log


def _rispetta_tetto_rischio(
    ticker_candidato: str,
    importo: float,
    stato: StatoBot,
    dati_per_ticker: dict,
    oggi: pd.Timestamp,
    sostituisce: str | None = None,
) -> bool:
    """
    True se investire 'importo' su 'ticker_candidato' NON sfora il tetto massimo
    su crypto/azioni insieme. Un ETF non ha mai un tetto (sempre True).

    'sostituisce' = ticker della posizione che verrebbe venduta per fare spazio
    (cambio-posizione): si valuta il portafoglio DOPO lo scambio.
    Se dopo l'operazione il candidato sarebbe l'unica posizione, il tetto non si
    applica (a meno che TETTO_ANCHE_CON_UNA_POSIZIONE sia True).
    """
    if config.categoria_di(ticker_candidato) != "rischioso":
        return True

    altre_posizioni = [t for t in stato.posizioni if t != sostituisce]
    if not altre_posizioni and not config.TETTO_ANCHE_CON_UNA_POSIZIONE:
        return True

    saldo_totale = stato.saldo_disponibile + _valore_posizioni(stato, dati_per_ticker, oggi)
    if saldo_totale <= 0:
        return True

    valore_rischioso = valore_per_categoria(stato, dati_per_ticker, oggi, "rischioso")
    if sostituisce is not None and config.categoria_di(sostituisce) == "rischioso":
        # la posizione venduta libera la sua quota rischiosa (importo e' gia' il suo valore)
        valore_rischioso -= importo
    return valore_rischioso + importo <= config.TETTO_RISCHIOSO_PCT * saldo_totale


def valuta_switch(
    stato: StatoBot,
    dati_per_ticker: dict[str, pd.DataFrame],
    oggi: pd.Timestamp,
    cautela: str,
    solo_categoria: str | None = None,
) -> list[dict]:
    """
    Per ogni posizione aperta (o solo quelle di 'solo_categoria', se indicato),
    controlla se esiste un'alternativa nettamente migliore (almeno
    SOGLIA_DIFFERENZA_CRITERI_SWITCH criteri favorevoli in piu'). Cambia SOLO
    se il guadagno gia' maturato in euro sulla posizione attuale copre la
    stima delle commissioni del cambio, E se il tetto di rischio lo permette.
    Altrimenti resta fermo, anche se l'alternativa sembra migliore.
    """
    eventi = []
    if not stato.posizioni:
        return eventi

    saldo_totale = stato.saldo_disponibile + _valore_posizioni(stato, dati_per_ticker, oggi)
    paniere_attuale = paniere_per_saldo(saldo_totale)
    dati_paniere = {t: _fino_a(dati_per_ticker[t], oggi) for t in paniere_attuale if t in dati_per_ticker}
    punteggi = scoring.valuta_paniere(dati_paniere)

    soglia_minima_criteri = config.LIVELLI_CAUTELA.get(cautela, 2)
    costo_stimato_switch = 2 * config.COMMISSIONE_STIMATA_EUR

    for ticker in list(stato.posizioni.keys()):
        if solo_categoria is not None and config.categoria_di(ticker) != solo_categoria:
            continue

        posizione = stato.posizioni[ticker]
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            continue

        variazione = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico
        punteggio_attuale = punteggi.get(ticker, {}).get("criteri_favorevoli", 0)
        valore_attuale_posizione = posizione.quota_investita * (1 + variazione)

        candidati_migliori = [
            (t, d) for t, d in punteggi.items()
            if t != ticker
            and t not in stato.posizioni
            and d["criteri_favorevoli"] >= soglia_minima_criteri
            and d["criteri_favorevoli"] >= punteggio_attuale + config.SOGLIA_DIFFERENZA_CRITERI_SWITCH
            and _rispetta_tetto_rischio(t, valore_attuale_posizione, stato, dati_per_ticker, oggi, sostituisce=ticker)
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
    log.extend(controlla_stop_loss_take_profit(stato, dati_per_ticker, oggi))

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
    dati_paniere = {t: _fino_a(dati_per_ticker[t], oggi) for t in paniere_attuale if t in dati_per_ticker}
    punteggi = scoring.valuta_paniere(dati_paniere)

    soglia_minima_criteri = config.LIVELLI_CAUTELA.get(cautela, 2)

    # Scegli il miglior candidato non ancora in portafoglio, rispettando il tetto di rischio
    # (un candidato crypto/azione che sforerebbe il tetto viene scartato: si ricade sugli ETF rimasti)
    candidati = [
        (ticker, dettagli)
        for ticker, dettagli in punteggi.items()
        if ticker not in stato.posizioni
        and dettagli["criteri_favorevoli"] >= soglia_minima_criteri
        and _rispetta_tetto_rischio(ticker, stato.saldo_disponibile, stato, dati_per_ticker, oggi)
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


def _fino_a(df: pd.DataFrame, oggi: pd.Timestamp) -> pd.DataFrame:
    """Solo i dati fino alla data di riferimento: lo scoring non deve mai vedere il futuro."""
    return df.loc[df.index <= oggi]


def data_piu_recente(dati_per_ticker: dict[str, pd.DataFrame]) -> pd.Timestamp:
    """
    L'ultima data per cui esiste almeno un prezzo valido, tra TUTTI i ticker.
    Serve come "oggi" dei cicli: usare solo il calendario degli ETF farebbe
    prezzare le crypto con il prezzo di venerdi' anche nel fine settimana.
    """
    ultime = []
    for df in dati_per_ticker.values():
        serie = df["Close"]
        if isinstance(serie, pd.DataFrame):
            serie = serie.iloc[:, 0]
        serie = serie.dropna()
        if not serie.empty:
            ultime.append(serie.index[-1])
    if not ultime:
        raise RuntimeError("Nessun dato di mercato disponibile: ciclo saltato.")
    return max(ultime)


def fotografia_valutazione(
    stato: StatoBot,
    dati_per_ticker: dict[str, pd.DataFrame],
    oggi: pd.Timestamp,
    cautela: str,
    posizioni_consentite: int,
    data_ora: str,
) -> dict:
    """
    "Cosa sta valutando Salvabot": il punteggio (criteri favorevoli su 3) di ogni
    candidato del paniere, in ordine di preferenza, piu' una nota in parole semplici
    che spiega perche' resta fermo o cosa farebbe. Solo informativa: non cambia nulla.
    """
    saldo_totale = stato.saldo_disponibile + _valore_posizioni(stato, dati_per_ticker, oggi)
    paniere = paniere_per_saldo(saldo_totale)
    da_valutare = list(dict.fromkeys(paniere + list(stato.posizioni)))  # anche le posizioni gia' aperte
    dati = {t: _fino_a(dati_per_ticker[t], oggi) for t in da_valutare if t in dati_per_ticker}
    punteggi = scoring.valuta_paniere(dati)
    soglia = config.LIVELLI_CAUTELA.get(cautela, 2)

    candidati = []
    for ticker, d in punteggi.items():
        vol = d["volatilita"]
        candidati.append({
            "ticker": ticker,
            "etichetta": config.etichetta_di(ticker),
            "criteri": int(d["criteri_favorevoli"]),
            "volatilita": None if vol != vol else round(float(vol), 3),
            "in_portafoglio": ticker in stato.posizioni,
        })
    # stesso ordine di preferenza usato per scegliere: piu' criteri, poi meno volatile
    candidati.sort(key=lambda c: (-c["criteri"], 9.0 if c["volatilita"] is None else c["volatilita"]))

    mancanti = [t for t in paniere if t not in dati_per_ticker]
    nota = _nota_valutazione(stato, candidati, soglia, posizioni_consentite, oggi, mancanti)
    return {"data_ora": data_ora, "soglia": soglia, "candidati": candidati, "nota": nota}


def _nota_valutazione(stato, candidati, soglia, posizioni_consentite, oggi, mancanti) -> str:
    tenute = [c for c in candidati if c["in_portafoglio"]]
    libere = [c for c in candidati if not c["in_portafoglio"]]
    migliore = libere[0] if libere else None
    parti = []

    if stato.in_raffreddamento_fino_al is not None and oggi < stato.in_raffreddamento_fino_al:
        parti.append(
            f"Modalità difensiva attiva fino al {stato.in_raffreddamento_fino_al.strftime('%d/%m')}: "
            f"nessun nuovo acquisto."
        )

    if tenute:
        parti.append("In portafoglio: " + ", ".join(f"{c['ticker']} ({c['criteri']}/3)" for c in tenute) + ".")
    else:
        parti.append("Nessuna posizione aperta.")

    if migliore:
        parti.append(f"Migliore alternativa: {migliore['ticker']} ({migliore['criteri']}/3).")

    if tenute and migliore:
        piu_debole = min(tenute, key=lambda c: c["criteri"])
        abbastanza_migliore = (
            migliore["criteri"] >= soglia
            and migliore["criteri"] >= piu_debole["criteri"] + config.SOGLIA_DIFFERENZA_CRITERI_SWITCH
        )
        if abbastanza_migliore:
            pos = stato.posizioni[piu_debole["ticker"]]
            guadagno = pos.quota_investita * pos.ultima_variazione_pct
            costo = 2 * config.COMMISSIONE_STIMATA_EUR
            parti.append(
                f"Un cambio non è ancora conveniente: guadagno attuale {guadagno:+.2f}\u20ac, "
                f"ne servirebbero più di {costo:.2f}\u20ac per coprire le commissioni stimate."
            )
        else:
            parti.append(
                f"Nessuna alternativa abbastanza migliore (servono almeno {soglia}/3 e "
                f"{config.SOGLIA_DIFFERENZA_CRITERI_SWITCH} criterio in più)."
            )
    elif not tenute and not any(c["criteri"] >= soglia for c in libere):
        parti.append(f"Nessun candidato raggiunge la soglia di convinzione ({soglia}/3): resto in attesa.")

    if stato.saldo_disponibile > 0.005 and len(stato.posizioni) >= posizioni_consentite:
        parti.append(
            f"Capitale libero {stato.saldo_disponibile:.2f}\u20ac ma posizioni già al massimo "
            f"({len(stato.posizioni)}/{posizioni_consentite})."
        )
    if mancanti:
        parti.append(f"Dati non disponibili oggi per: {', '.join(mancanti)}.")
    return " ".join(parti)


def aggiorna_variazioni_posizioni(
    stato: StatoBot, dati_per_ticker: dict[str, pd.DataFrame], oggi: pd.Timestamp
) -> None:
    """Aggiorna su ogni posizione la variazione % dall'acquisto (mostrata sulla pagina)."""
    for ticker, posizione in stato.posizioni.items():
        prezzo_attuale = _ultimo_prezzo(dati_per_ticker[ticker], oggi)
        if prezzo_attuale is None:
            continue
        posizione.ultima_variazione_pct = (prezzo_attuale - posizione.prezzo_di_carico) / posizione.prezzo_di_carico


def _ultimo_prezzo(df: pd.DataFrame, fino_a: pd.Timestamp) -> float | None:
    serie = df["Close"]
    if isinstance(serie, pd.DataFrame):
        serie = serie.iloc[:, 0]
    serie_filtrata = serie[serie.index <= fino_a].dropna()  # scarta eventuali prezzi mancanti/incompleti
    if serie_filtrata.empty:
        return None
    valore = float(serie_filtrata.iloc[-1])
    return None if pd.isna(valore) else valore


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

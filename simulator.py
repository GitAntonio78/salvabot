"""
Backtest di Salvabot: rifa' girare le STESSE regole del ciclo principale giorno per giorno
su una serie storica, per vedere come si sarebbe comportato in passato con tutto il paniere
(ETF + crypto + azioni).

Cosa e' fedele alla realta':
- stesse regole di scelta, stop-loss/take-profit per categoria, tetto di rischio, cambio con
  controllo commissioni (e' lo stesso decision_engine del bot vero);
- a ogni giorno lo scoring vede SOLO i dati fino a quel giorno (mai il futuro).

Cosa e' semplificato (da tenere presente leggendo i risultati):
- un solo passaggio al giorno: i 3 controlli di sicurezza intraday non sono simulati,
  quindi uno stop-loss su crypto/azioni scatta al prezzo di chiusura, non nel momento esatto;
- le commissioni (COMMISSIONE_STIMATA_EUR a operazione) sono sottratte alla fine, non durante;
- il passato non garantisce nulla sul futuro.
"""

import pandas as pd

import config
import data_provider
import decision_engine

GIORNI_DI_RISCALDAMENTO = 220  # servono ~200 giorni di storia per le medie mobili dello scoring


def _serie_close(df: pd.DataFrame) -> pd.Series:
    serie = df["Close"]
    if isinstance(serie, pd.DataFrame):
        serie = serie.iloc[:, 0]
    return serie.dropna()


def _drawdown_massimo(curva: list[float]) -> float:
    """Peggior calo percentuale dal massimo raggiunto (es. -0.12 = -12%)."""
    massimo, peggiore = float("-inf"), 0.0
    for valore in curva:
        massimo = max(massimo, valore)
        if massimo > 0:
            peggiore = min(peggiore, valore / massimo - 1)
    return peggiore


def esegui_demo(
    saldo_iniziale: float = config.SALDO_INIZIALE_DEFAULT,
    cautela: str = config.CAUTELA_DEFAULT,
    giorni_storico: int = 1100,
    posizioni_consentite: int = 1,
    ticker_indice_riferimento: str = "VWCE.DE",
    richiedi_dati_reali: bool = False,
) -> dict:
    tutti_i_ticker = sorted(
        {t for _, lista in config.PANIERE_PER_FASCIA_DI_SALDO for t in lista} | set(config.PANIERE_RISCHIOSO)
    )
    dati_per_ticker = data_provider.scarica_paniere(tutti_i_ticker, giorni=giorni_storico)

    if richiedi_dati_reali:
        non_reali = [t for t in tutti_i_ticker if data_provider.ORIGINE_DATI.get(t) != "reale"]
        if non_reali:
            raise RuntimeError(
                f"Backtest annullato: dati reali non disponibili per {', '.join(non_reali)}. "
                f"Un backtest su prezzi inventati non avrebbe alcun significato."
            )
    data_provider.verifica_dati(dati_per_ticker, [ticker_indice_riferimento])

    serie_indice = _serie_close(dati_per_ticker[ticker_indice_riferimento])
    if len(serie_indice) <= GIORNI_DI_RISCALDAMENTO + 5:
        raise RuntimeError("Storia troppo corta per il backtest: aumenta i giorni.")
    date_simulate = serie_indice.index[GIORNI_DI_RISCALDAMENTO:]

    stato = decision_engine.StatoBot(saldo_disponibile=saldo_iniziale)
    log_completo: list[str] = []
    curva: list[float] = []
    giorni_per_categoria = {"ETF": 0.0, "Crypto": 0.0, "Azione": 0.0, "Liquidita'": 0.0}
    acquisti_per_categoria = {"ETF": 0, "Crypto": 0, "Azione": 0}
    conteggio = {"investito": 0, "stop_loss": 0, "take_profit": 0, "switch": 0}

    for oggi in date_simulate:
        eventi = decision_engine.decidi_ciclo(
            stato=stato,
            dati_per_ticker=dati_per_ticker,
            prezzi_indice_riferimento=serie_indice[serie_indice.index <= oggi],
            oggi=oggi,
            cautela=cautela,
            posizioni_consentite=posizioni_consentite,
        )
        for evento in eventi:
            if evento["tipo"] in conteggio:
                conteggio[evento["tipo"]] += 1
            if evento["tipo"] != "attesa":
                log_completo.append(f"[{oggi.date()}] {evento['messaggio']}")
            if evento["tipo"] == "investito":
                nuovo = list(stato.posizioni)[-1]
                acquisti_per_categoria[config.etichetta_di(nuovo)] += 1

        curva.append(stato.saldo_disponibile + decision_engine._valore_posizioni(stato, dati_per_ticker, oggi))
        if stato.posizioni:
            for t in stato.posizioni:
                giorni_per_categoria[config.etichetta_di(t)] += 1.0 / len(stato.posizioni)
        else:
            giorni_per_categoria["Liquidita'"] += 1.0

    n_operazioni = conteggio["investito"] + conteggio["stop_loss"] + conteggio["take_profit"] + conteggio["switch"]
    commissioni = n_operazioni * config.COMMISSIONE_STIMATA_EUR
    lordo = curva[-1]
    netto = lordo - commissioni

    # Confronto con "non fare niente": comprare VWCE.DE il primo giorno e tenerlo
    prezzi_etf = serie_indice[serie_indice.index >= date_simulate[0]]
    curva_etf = [saldo_iniziale * p / prezzi_etf.iloc[0] for p in prezzi_etf]
    bench_netto = curva_etf[-1] - config.COMMISSIONE_STIMATA_EUR  # un solo acquisto

    def pct(finale: float) -> float:
        return round((finale / saldo_iniziale - 1) * 100, 2)

    metriche = {
        "periodo_inizio": str(date_simulate[0].date()),
        "periodo_fine": str(date_simulate[-1].date()),
        "giorni_simulati": len(date_simulate),
        "saldo_iniziale": saldo_iniziale,
        "saldo_finale_lordo": round(lordo, 2),
        "n_operazioni": n_operazioni,
        "commissioni_stimate": round(commissioni, 2),
        "saldo_finale_netto": round(netto, 2),
        "rendimento_netto_pct": pct(netto),
        "drawdown_max_pct": round(_drawdown_massimo(curva) * 100, 1),
        "benchmark_netto": round(bench_netto, 2),
        "benchmark_rendimento_netto_pct": pct(bench_netto),
        "benchmark_drawdown_max_pct": round(_drawdown_massimo(curva_etf) * 100, 1),
        "giorni_per_categoria": {k: round(v) for k, v in giorni_per_categoria.items()},
        "acquisti_per_categoria": acquisti_per_categoria,
        "stop_loss": conteggio["stop_loss"],
        "take_profit": conteggio["take_profit"],
        "cambi": conteggio["switch"],
        "dati_reali_usati": data_provider.tutti_reali(),
        "ticker_non_reali": data_provider.ticker_non_reali(),
    }
    return {"log": log_completo, "metriche": metriche}

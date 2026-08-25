"""
Modulo di scoring.

Per ogni ETF calcola gli indicatori discussi nel progetto:
- volatilità storica
- drawdown massimo
- trend (medie mobili 50/200 giorni)
- momentum (RSI)

Poi traduce questi numeri in un giudizio semplice: quanti dei 3
criteri principali sono "favorevoli" in questo momento.
"""

import numpy as np
import pandas as pd


def volatilita_storica(prezzi: pd.Series, finestra: int = 90) -> float:
    """Deviazione standard annualizzata dei rendimenti giornalieri."""
    rendimenti = prezzi.pct_change().dropna().tail(finestra)
    if len(rendimenti) < 2:
        return float("nan")
    return float(rendimenti.std() * np.sqrt(252))


def drawdown_massimo(prezzi: pd.Series) -> float:
    """Perdita percentuale peggiore rispetto al massimo storico."""
    massimo_progressivo = prezzi.cummax()
    drawdown = (prezzi - massimo_progressivo) / massimo_progressivo
    return float(drawdown.min())


def trend_medie_mobili(prezzi: pd.Series, corta: int = 50, lunga: int = 200) -> str:
    """'positivo' se la media mobile corta è sopra quella lunga, altrimenti 'negativo'."""
    if len(prezzi) < lunga:
        return "indeterminato"
    mm_corta = prezzi.rolling(corta).mean().iloc[-1]
    mm_lunga = prezzi.rolling(lunga).mean().iloc[-1]
    return "positivo" if mm_corta > mm_lunga else "negativo"


def rsi(prezzi: pd.Series, periodo: int = 14) -> float:
    """Relative Strength Index, per capire se un asset è ipercomprato/ipervenduto."""
    delta = prezzi.diff().dropna()
    guadagni = delta.clip(lower=0)
    perdite = -delta.clip(upper=0)
    media_guadagni = guadagni.rolling(periodo).mean()
    media_perdite = perdite.rolling(periodo).mean()
    rs = media_guadagni / media_perdite.replace(0, np.nan)
    valore = 100 - (100 / (1 + rs))
    return float(valore.iloc[-1]) if not valore.empty else float("nan")


def calcola_scoring(prezzi: pd.Series, soglia_volatilita: float = 0.20) -> dict:
    """
    Calcola i 3 criteri principali e restituisce un dizionario con:
    - i valori grezzi degli indicatori
    - quanti criteri su 3 sono favorevoli in questo momento
    """
    vol = volatilita_storica(prezzi)
    dd = drawdown_massimo(prezzi)
    trend = trend_medie_mobili(prezzi)
    valore_rsi = rsi(prezzi)

    criteri_favorevoli = 0
    dettagli = {}

    # Criterio 1: trend positivo
    trend_ok = trend == "positivo"
    criteri_favorevoli += int(trend_ok)
    dettagli["trend"] = trend

    # Criterio 2: volatilità sotto soglia (mercato non troppo agitato)
    volatilita_ok = (not np.isnan(vol)) and vol < soglia_volatilita
    criteri_favorevoli += int(volatilita_ok)
    dettagli["volatilita"] = vol

    # Criterio 3: momentum non ipercomprato (RSI sotto 70, quindi ancora margine)
    momentum_ok = (not np.isnan(valore_rsi)) and valore_rsi < 70
    criteri_favorevoli += int(momentum_ok)
    dettagli["rsi"] = valore_rsi

    dettagli["drawdown_massimo"] = dd
    dettagli["criteri_favorevoli"] = criteri_favorevoli
    dettagli["criteri_totali"] = 3
    return dettagli


def valuta_paniere(dati_per_ticker: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Applica calcola_scoring a ogni ETF del paniere."""
    risultati = {}
    for ticker, df in dati_per_ticker.items():
        colonna_prezzo = df["Close"]
        if isinstance(colonna_prezzo, pd.DataFrame):  # yfinance a volte restituisce multi-colonna
            colonna_prezzo = colonna_prezzo.iloc[:, 0]
        risultati[ticker] = calcola_scoring(colonna_prezzo)
    return risultati

"""
Fornitore di dati di mercato.

Prova prima a usare yfinance (dati reali). Se non è disponibile
(pacchetto non installato o nessuna connessione), usa un generatore
di dati sintetici, cosi' puoi comunque far girare e testare tutta
la logica di Salvabot offline, prima di collegarlo a dati veri.
"""

import hashlib

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    YFINANCE_DISPONIBILE = True
except ImportError:
    YFINANCE_DISPONIBILE = False


def _genera_dati_sintetici(ticker: str, giorni: int = 400, seed: int | None = None) -> pd.DataFrame:
    """Genera un prezzo storico plausibile con un random walk (solo per test offline)."""
    seed_stabile = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed if seed is not None else seed_stabile)
    date = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=giorni)
    rendimenti_giornalieri = rng.normal(loc=0.0003, scale=0.008, size=len(date))
    prezzi = 100 * np.cumprod(1 + rendimenti_giornalieri)
    return pd.DataFrame({"Close": prezzi}, index=date)


def scarica_storico(ticker: str, giorni: int = 400) -> pd.DataFrame:
    """
    Restituisce un DataFrame con almeno la colonna 'Close'.
    Usa yfinance se disponibile, altrimenti dati sintetici.
    """
    if YFINANCE_DISPONIBILE:
        try:
            dati = yf.download(ticker, period=f"{giorni}d", progress=False, auto_adjust=True)
            if dati is not None and not dati.empty:
                colonna_prezzo = dati["Close"]
                if isinstance(colonna_prezzo, pd.DataFrame):
                    colonna_prezzo = colonna_prezzo.iloc[:, 0]
                # Scarta le righe senza un prezzo di chiusura valido: capita per la
                # giornata odierna se il mercato non ha ancora chiuso (o non ha
                # ancora aperto) quando Salvabot gira - meglio usare l'ultimo
                # prezzo di chiusura vero, mai un dato mancante/incompleto.
                dati = dati.loc[colonna_prezzo.notna()]
                if not dati.empty:
                    return dati
        except Exception:
            pass  # ricade sui dati sintetici se il download fallisce (es. no internet)

    return _genera_dati_sintetici(ticker, giorni)


def scarica_paniere(tickers: list[str], giorni: int = 400) -> dict[str, pd.DataFrame]:
    """Scarica lo storico per una lista di ticker."""
    return {t: scarica_storico(t, giorni) for t in tickers}

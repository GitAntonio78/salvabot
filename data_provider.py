"""
Fornitore di dati di mercato.

Due modalità:
- NORMALE (sul tuo computer / nei test): prova yfinance; se non c'è connessione usa
  dati sintetici, così si può far girare e testare la logica anche offline.
- SOLO DATI REALI (variabile d'ambiente SALVABOT_SOLO_DATI_REALI=1, impostata nei
  workflow di GitHub): mai prezzi inventati. Se un ticker non si scarica dopo qualche
  tentativo viene semplicemente omesso, e chi lo usa decide cosa fare
  (vedi verifica_dati: un ciclo che ne ha bisogno si ferma senza salvare nulla).

Per ogni ticker si ricorda se i dati sono 'reale', 'sintetico' o 'mancante'.
"""

import hashlib
import os
import time

import numpy as np
import pandas as pd

try:
    import yfinance as yf
    YFINANCE_DISPONIBILE = True
except ImportError:
    YFINANCE_DISPONIBILE = False

TENTATIVI_DOWNLOAD = 3
PAUSA_TRA_TENTATIVI_SECONDI = 3

# ticker -> 'reale' | 'sintetico' | 'mancante' (aggiornato a ogni scaricamento)
ORIGINE_DATI: dict[str, str] = {}


def solo_dati_reali() -> bool:
    """True se siamo in produzione: vietato usare prezzi sintetici."""
    return os.environ.get("SALVABOT_SOLO_DATI_REALI") == "1"


def _genera_dati_sintetici(ticker: str, giorni: int = 400, seed: int | None = None) -> pd.DataFrame:
    """Genera un prezzo storico plausibile con un random walk (solo per test offline)."""
    seed_stabile = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % (2**32)
    rng = np.random.default_rng(seed if seed is not None else seed_stabile)
    date = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=giorni)
    rendimenti_giornalieri = rng.normal(loc=0.0003, scale=0.008, size=len(date))
    prezzi = 100 * np.cumprod(1 + rendimenti_giornalieri)
    return pd.DataFrame({"Close": prezzi}, index=date)


def _scarica_da_yfinance(ticker: str, giorni: int) -> pd.DataFrame | None:
    """Un tentativo di download. None se fallisce o non c'è nessun prezzo valido."""
    try:
        dati = yf.download(ticker, period=f"{giorni}d", progress=False, auto_adjust=True)
        if dati is None or dati.empty:
            return None
        colonna_prezzo = dati["Close"]
        if isinstance(colonna_prezzo, pd.DataFrame):
            colonna_prezzo = colonna_prezzo.iloc[:, 0]
        # Scarta le righe senza un prezzo di chiusura valido: capita per la giornata
        # odierna se il mercato non ha ancora chiuso quando Salvabot gira - meglio
        # usare l'ultimo prezzo di chiusura vero, mai un dato mancante/incompleto.
        dati = dati.loc[colonna_prezzo.notna()]
        return dati if not dati.empty else None
    except Exception:
        return None


def scarica_storico(ticker: str, giorni: int = 400) -> pd.DataFrame | None:
    """
    Restituisce un DataFrame con almeno la colonna 'Close', oppure None se in
    modalità SOLO DATI REALI non è stato possibile scaricare dati veri.
    """
    if YFINANCE_DISPONIBILE:
        tentativi = TENTATIVI_DOWNLOAD if solo_dati_reali() else 1
        for n in range(tentativi):
            dati = _scarica_da_yfinance(ticker, giorni)
            if dati is not None:
                ORIGINE_DATI[ticker] = "reale"
                return dati
            if n < tentativi - 1:
                time.sleep(PAUSA_TRA_TENTATIVI_SECONDI)

    if solo_dati_reali():
        ORIGINE_DATI[ticker] = "mancante"
        return None

    ORIGINE_DATI[ticker] = "sintetico"
    return _genera_dati_sintetici(ticker, giorni)


def scarica_paniere(tickers: list[str], giorni: int = 400) -> dict[str, pd.DataFrame]:
    """Scarica lo storico per una lista di ticker. I ticker non disponibili sono omessi."""
    risultato = {}
    for t in tickers:
        df = scarica_storico(t, giorni)
        if df is not None:
            risultato[t] = df
    return risultato


def verifica_dati(dati_per_ticker: dict, obbligatori: list[str]) -> None:
    """
    Ferma il ciclo (senza salvare nulla) se mancano i dati di un ticker indispensabile,
    es. quello di una posizione aperta: meglio saltare un giro che decidere alla cieca.
    """
    mancanti = [t for t in dict.fromkeys(obbligatori) if t not in dati_per_ticker]
    if mancanti:
        raise RuntimeError(
            f"Dati di mercato non disponibili per: {', '.join(mancanti)}. "
            f"Ciclo saltato per sicurezza: nessuna modifica salvata, si riprova al prossimo."
        )


def tutti_reali() -> bool:
    """True se tutti i ticker scaricati finora sono dati veri (nessuno sintetico)."""
    return bool(ORIGINE_DATI) and all(o == "reale" for o in ORIGINE_DATI.values())


def ticker_non_reali() -> list[str]:
    return sorted(t for t, o in ORIGINE_DATI.items() if o != "reale")

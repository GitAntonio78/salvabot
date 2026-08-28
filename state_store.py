"""
Salvataggio/ricarica dello stato di Salvabot.

Senza questo modulo, ogni volta che lo script viene rilanciato Salvabot
"dimentica" tutto e riparte da zero. Qui lo stato completo (saldo,
posizioni aperte, salvadanaio, storico, raffreddamento post-crash)
viene salvato su un file JSON e ricaricato al riavvio.

E' la base tecnica necessaria prima di far girare Salvabot su un
server continuo: un processo che si riavvia (es. dopo un aggiornamento
o un riavvio del server) deve poter riprendere da dove aveva lasciato.
"""

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from decision_engine import Posizione, StatoBot
from portfolio import Portafoglio

FILE_STATO_DEFAULT = Path("stato_salvabot.json")


def salva_stato(stato: StatoBot, portafoglio: Portafoglio, percorso: Path = FILE_STATO_DEFAULT) -> None:
    """Scrive lo stato completo su file JSON."""
    dati = {
        "stato_bot": {
            "saldo_disponibile": stato.saldo_disponibile,
            "posizioni": {
                ticker: asdict(posizione) for ticker, posizione in stato.posizioni.items()
            },
            "in_raffreddamento_fino_al": (
                stato.in_raffreddamento_fino_al.isoformat()
                if stato.in_raffreddamento_fino_al is not None
                else None
            ),
        },
        "portafoglio": {
            "saldo_investito": portafoglio.saldo_investito,
            "salvadanaio": portafoglio.salvadanaio,
            "storico_saldo": portafoglio.storico_saldo,
            "storico_eventi": portafoglio.storico_eventi,
            "storico_punti": portafoglio.storico_punti,
        },
    }

    # Scrittura "atomica": prima su file temporaneo, poi rinomina.
    # Evita di corrompere il file se il processo si interrompe a metà scrittura.
    percorso_temporaneo = percorso.with_suffix(".tmp")
    percorso_temporaneo.write_text(json.dumps(dati, indent=2, ensure_ascii=False))
    percorso_temporaneo.replace(percorso)


def carica_stato(percorso: Path = FILE_STATO_DEFAULT) -> tuple[StatoBot, Portafoglio] | None:
    """
    Rilegge lo stato da file JSON. Restituisce None se il file non esiste
    ancora (primo avvio di sempre, nessun errore).
    """
    if not percorso.exists():
        return None

    dati = json.loads(percorso.read_text())

    sb = dati["stato_bot"]
    posizioni = {
        ticker: Posizione(**valori) for ticker, valori in sb["posizioni"].items()
    }
    in_raffreddamento = (
        pd.Timestamp(sb["in_raffreddamento_fino_al"])
        if sb["in_raffreddamento_fino_al"] is not None
        else None
    )
    stato = StatoBot(
        saldo_disponibile=sb["saldo_disponibile"],
        posizioni=posizioni,
        in_raffreddamento_fino_al=in_raffreddamento,
    )

    pf = dati["portafoglio"]
    portafoglio = Portafoglio(
        saldo_investito=pf["saldo_investito"],
        salvadanaio=pf["salvadanaio"],
        storico_saldo=pf["storico_saldo"],
        storico_eventi=pf.get("storico_eventi", []),
        storico_punti=pf.get("storico_punti", []),
    )

    return stato, portafoglio


def stato_esistente(percorso: Path = FILE_STATO_DEFAULT) -> bool:
    """Utile per sapere se e' il primo avvio (serve il saldo iniziale) o no."""
    return percorso.exists()

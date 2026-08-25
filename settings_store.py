"""
Impostazioni persistenti di Salvabot.

config.py contiene i DEFAULT di partenza. Le impostazioni effettive
(che possono cambiare nel tempo: dall'utente in fase di setup, o da
una proposta di auto-valutazione confermata) vivono qui, su file,
cosi' sopravvivono al riavvio esattamente come lo stato del portafoglio.
"""

import json
from pathlib import Path

import config

FILE_IMPOSTAZIONI_DEFAULT = Path("impostazioni_salvabot.json")

CHIAVI_MODIFICABILI = ("STOP_LOSS_PCT", "TAKE_PROFIT_PCT", "CAUTELA")


def impostazioni_di_default() -> dict:
    return {
        "STOP_LOSS_PCT": config.STOP_LOSS_PCT,
        "TAKE_PROFIT_PCT": config.TAKE_PROFIT_PCT,
        "CAUTELA": config.CAUTELA_DEFAULT,
    }


def carica_impostazioni(percorso: Path = FILE_IMPOSTAZIONI_DEFAULT) -> dict:
    """Ricarica le impostazioni salvate, o restituisce i default se non esistono ancora."""
    if not percorso.exists():
        return impostazioni_di_default()
    return json.loads(percorso.read_text())


def salva_impostazioni(impostazioni: dict, percorso: Path = FILE_IMPOSTAZIONI_DEFAULT) -> None:
    percorso_temporaneo = percorso.with_suffix(".tmp")
    percorso_temporaneo.write_text(json.dumps(impostazioni, indent=2, ensure_ascii=False))
    percorso_temporaneo.replace(percorso)


def aggiorna_impostazione(
    chiave: str, valore, percorso: Path = FILE_IMPOSTAZIONI_DEFAULT
) -> dict:
    """Aggiorna una singola impostazione e la salva. Restituisce le impostazioni aggiornate."""
    if chiave not in CHIAVI_MODIFICABILI:
        raise ValueError(f"'{chiave}' non e' un'impostazione modificabile. Valide: {CHIAVI_MODIFICABILI}")
    impostazioni = carica_impostazioni(percorso)
    impostazioni[chiave] = valore
    salva_impostazioni(impostazioni, percorso)
    return impostazioni


def applica_a_config(impostazioni: dict) -> None:
    """Applica le impostazioni caricate al modulo config per la sessione corrente."""
    config.STOP_LOSS_PCT = impostazioni["STOP_LOSS_PCT"]
    config.TAKE_PROFIT_PCT = impostazioni["TAKE_PROFIT_PCT"]

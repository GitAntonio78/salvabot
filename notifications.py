"""
Coda delle notifiche di Salvabot.

Finché non esiste un'app o un canale di invio reale (push, email, ecc.),
le notifiche importanti vengono scritte qui, su file, in ordine cronologico
e con lo stato "letta/non letta". Il giorno in cui costruiremo l'app o un
canale di invio, basterà leggerle da qui invece di reinventare la logica.

Tipi di notifica usati:
- 'salvadanaio'   -> proposta di mettere via una parte del saldo
- 'espansione'    -> proposta di provare crypto/azioni
- 'autovalutazione' -> proposta di modifica di un parametro
- 'crash'         -> attivazione della modalità difensiva (informativa, non richiede conferma)
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

FILE_NOTIFICHE_DEFAULT = Path("notifiche_salvabot.json")


@dataclass
class Notifica:
    tipo: str
    messaggio: str
    data: str
    richiede_conferma: bool
    letta: bool = False
    id: int = field(default=0)


def _carica_tutte(percorso: Path) -> list[dict]:
    if not percorso.exists():
        return []
    return json.loads(percorso.read_text())


def _salva_tutte(notifiche: list[dict], percorso: Path) -> None:
    percorso_temporaneo = percorso.with_suffix(".tmp")
    percorso_temporaneo.write_text(json.dumps(notifiche, indent=2, ensure_ascii=False))
    percorso_temporaneo.replace(percorso)


def invia(
    tipo: str,
    messaggio: str,
    data: str,
    richiede_conferma: bool = False,
    percorso: Path = FILE_NOTIFICHE_DEFAULT,
) -> Notifica:
    """
    Aggiunge una notifica alla coda persistente. Se esiste gia' una
    notifica NON LETTA dello stesso tipo (es. il ciclo e' girato piu'
    volte nello stesso giorno, magari lanciato a mano), aggiorna quella
    esistente invece di crearne una seconda - cosi' resta sempre una
    sola proposta attiva per tipo, con la data/ora piu' recente.
    """
    notifiche = _carica_tutte(percorso)

    for n in notifiche:
        if n["tipo"] == tipo and not n["letta"]:
            n["messaggio"] = messaggio
            n["data"] = data
            n["richiede_conferma"] = richiede_conferma
            _salva_tutte(notifiche, percorso)
            return Notifica(**n)

    prossimo_id = (max((n["id"] for n in notifiche), default=0)) + 1
    nuova = Notifica(tipo=tipo, messaggio=messaggio, data=data, richiede_conferma=richiede_conferma, id=prossimo_id)
    notifiche.append(asdict(nuova))
    _salva_tutte(notifiche, percorso)
    return nuova


def non_lette(percorso: Path = FILE_NOTIFICHE_DEFAULT) -> list[dict]:
    return [n for n in _carica_tutte(percorso) if not n["letta"]]


def segna_come_letta(id_notifica: int, percorso: Path = FILE_NOTIFICHE_DEFAULT) -> None:
    notifiche = _carica_tutte(percorso)
    for n in notifiche:
        if n["id"] == id_notifica:
            n["letta"] = True
    _salva_tutte(notifiche, percorso)

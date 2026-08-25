"""
Auto-valutazione di Salvabot.

Analizza gli eventi e il saldo recenti per capire se qualcosa non sta
andando come dovrebbe, e in tal caso PROPONE una modifica specifica e
comprensibile — non cambia mai nulla in autonomia. L'utente conferma
o rifiuta ogni proposta.

Le proposte sono intenzionalmente in linguaggio semplice, coerenti con
il resto dell'app pensata per chi non mastica di finanza.
"""

from dataclasses import dataclass

import config
import settings_store
from portfolio import Portafoglio


@dataclass
class Proposta:
    problema: str
    proposta: str
    parametro: str        # nome del parametro in config.py da modificare
    valore_suggerito: float | str


def _drawdown_da_massimo(storico_saldo: list[float]) -> float:
    if len(storico_saldo) < 2:
        return 0.0
    massimo = max(storico_saldo)
    if massimo <= 0:
        return 0.0
    return (storico_saldo[-1] - massimo) / massimo


def valuta(portafoglio: Portafoglio, cautela_attuale: str = config.CAUTELA_DEFAULT) -> list[Proposta]:
    """
    Analizza lo storico recente e restituisce una lista di proposte
    (puo' essere vuota, se va tutto bene). Non modifica nulla.
    """
    proposte: list[Proposta] = []

    eventi_recenti = portafoglio.storico_eventi[-config.VALUTAZIONE_FINESTRA_CICLI:]

    if len(eventi_recenti) < config.VALUTAZIONE_CICLI_MINIMI:
        return proposte  # non ci sono ancora abbastanza dati per dire qualcosa di sensato

    conteggio = {"stop_loss": 0, "take_profit": 0, "attesa": 0, "investito": 0, "difensiva": 0}
    for evento in eventi_recenti:
        conteggio[evento["tipo"]] = conteggio.get(evento["tipo"], 0) + 1

    totale = len(eventi_recenti)

    # --- Pattern 1: troppi stop-loss ravvicinati ---
    if conteggio["stop_loss"] >= config.SOGLIA_TROPPI_STOP_LOSS:
        proposte.append(
            Proposta(
                problema=(
                    f"Negli ultimi {totale} cicli lo stop-loss e' scattato {conteggio['stop_loss']} volte: "
                    f"forse la soglia attuale ({config.STOP_LOSS_PCT:.0%}) e' troppo stretta per le normali "
                    f"oscillazioni del mercato."
                ),
                proposta=f"Allargare lo stop-loss da {config.STOP_LOSS_PCT:.0%} a -13%",
                parametro="STOP_LOSS_PCT",
                valore_suggerito=-0.13,
            )
        )

    # --- Pattern 2: resta quasi sempre in attesa (forse troppo cauto) ---
    quota_attesa = conteggio["attesa"] / totale if totale else 0
    if quota_attesa >= config.SOGLIA_TROPPA_ATTESA_PCT:
        prossimo_livello = {"prudente": "equilibrato", "equilibrato": "dinamico", "dinamico": None}
        suggerito = prossimo_livello.get(cautela_attuale)
        if suggerito:
            proposte.append(
                Proposta(
                    problema=(
                        f"Negli ultimi {totale} cicli sono rimasto fermo il {quota_attesa:.0%} delle volte: "
                        f"forse il livello di cautela '{cautela_attuale}' mi impedisce di cogliere occasioni valide."
                    ),
                    proposta=f"Passare da '{cautela_attuale}' a '{suggerito}'",
                    parametro="CAUTELA",
                    valore_suggerito=suggerito,
                )
            )

    # --- Pattern 3: drawdown complessivo preoccupante ---
    drawdown = _drawdown_da_massimo(portafoglio.storico_saldo)
    if drawdown <= config.SOGLIA_DRAWDOWN_PREOCCUPANTE_PCT:
        proposte.append(
            Proposta(
                problema=(
                    f"Il saldo e' sceso del {abs(drawdown):.0%} rispetto al massimo raggiunto: "
                    f"e' oltre quello che mi aspetterei con la mia strategia attuale."
                ),
                proposta="Passare temporaneamente a un livello di cautela piu' prudente",
                parametro="CAUTELA",
                valore_suggerito="prudente",
            )
        )

    return proposte


def applica_proposta(proposta: Proposta) -> str:
    """
    Da chiamare SOLO dopo la conferma esplicita dell'utente.
    Salva la modifica in modo permanente (sopravvive al riavvio) e
    restituisce un messaggio di conferma leggibile.
    """
    chiave = "CAUTELA" if proposta.parametro == "CAUTELA" else proposta.parametro
    settings_store.aggiorna_impostazione(chiave, proposta.valore_suggerito)

    if proposta.parametro == "CAUTELA":
        return f"Livello di cautela aggiornato e salvato: '{proposta.valore_suggerito}'."
    config.STOP_LOSS_PCT = proposta.valore_suggerito if proposta.parametro == "STOP_LOSS_PCT" else config.STOP_LOSS_PCT
    config.TAKE_PROFIT_PCT = proposta.valore_suggerito if proposta.parametro == "TAKE_PROFIT_PCT" else config.TAKE_PROFIT_PCT
    return f"Parametro {proposta.parametro} aggiornato e salvato a {proposta.valore_suggerito}."

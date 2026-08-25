"""
Gestisce una conferma/rifiuto arrivato come issue GitHub.

Il titolo della issue e' nel formato "salvabot:<azione>:<id_notifica>"
(generato da genera_pagina.py). Questo script:
1. Recupera la notifica corrispondente
2. Se e' una conferma, applica davvero la scelta (salvadanaio, espansione,
   o una proposta di auto-valutazione)
3. Segna la notifica come letta
4. Rigenera la pagina web aggiornata

Pensato per essere lanciato dal workflow "gestisci_conferma.yml", con
titolo e corpo della issue passati come variabili d'ambiente.
"""

import os
import re
import sys

import genera_pagina
import notifications
import self_evaluation
import settings_store
import state_store


def estrai_importo(corpo_issue: str, default: float = 0.0) -> float:
    """Cerca un numero nel corpo della issue (l'utente puo' averlo modificato)."""
    corrispondenza = re.search(r"(\d+(?:[.,]\d+)?)\s*$", corpo_issue.strip())
    if corrispondenza:
        return float(corrispondenza.group(1).replace(",", "."))
    return default


def gestisci(titolo_issue: str, corpo_issue: str) -> str:
    corrispondenza = re.match(r"salvabot:(conferma|ignora):(\d+)", titolo_issue.strip())
    if not corrispondenza:
        return f"Titolo non riconosciuto, nessuna azione eseguita: '{titolo_issue}'"

    azione, id_notifica = corrispondenza.group(1), int(corrispondenza.group(2))

    notifiche = notifications._carica_tutte(notifications.FILE_NOTIFICHE_DEFAULT)
    notifica = next((n for n in notifiche if n["id"] == id_notifica), None)

    if notifica is None:
        return f"Notifica {id_notifica} non trovata (forse gia' gestita)."

    messaggio_risultato = f"Notifica {id_notifica} ({notifica['tipo']}) ignorata."

    if azione == "conferma":
        if notifica["tipo"] == "salvadanaio":
            importo = estrai_importo(corpo_issue, default=0.0)
            stato_e_portafoglio = state_store.carica_stato()
            if stato_e_portafoglio is not None:
                stato, portafoglio = stato_e_portafoglio
                portafoglio.applica_scelta_salvadanaio(importo)
                state_store.salva_stato(stato, portafoglio)
                messaggio_risultato = f"Salvadanaio aggiornato: +{importo:.2f} EUR."

        elif notifica["tipo"] == "espansione":
            importo = estrai_importo(corpo_issue, default=0.0)
            # Nota: l'apertura vera e propria della categoria crypto/azioni
            # richiede ancora il collegamento al broker (fase successiva).
            # Per ora registriamo l'intenzione confermata dall'utente.
            messaggio_risultato = (
                f"Espansione confermata con {importo:.2f} EUR. "
                f"Verra' attivata quando sara' collegato il broker."
            )

        elif notifica["tipo"] == "autovalutazione":
            impostazioni = settings_store.carica_impostazioni()
            # In questa versione semplice, riapplichiamo l'ultima proposta nota
            # rieseguendo la valutazione sullo stato attuale.
            stato_e_portafoglio = state_store.carica_stato()
            if stato_e_portafoglio is not None:
                _, portafoglio = stato_e_portafoglio
                proposte = self_evaluation.valuta(portafoglio, cautela_attuale=impostazioni["CAUTELA"])
                if proposte:
                    messaggio_risultato = self_evaluation.applica_proposta(proposte[0])

    notifications.segna_come_letta(id_notifica)
    genera_pagina.genera()
    return messaggio_risultato


if __name__ == "__main__":
    titolo = os.environ.get("ISSUE_TITLE", "")
    corpo = os.environ.get("ISSUE_BODY", "")
    risultato = gestisci(titolo, corpo)
    print(risultato)

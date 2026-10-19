# Salvabot

Bot di investimento paziente ("stile tartaruga"), in **demo** (nessun soldo vero, nessun broker collegato).
Gira da solo su GitHub Actions e si controlla da una pagina web, anche da smartphone.
Repository: GitAntonio78/salvabot (pubblico in demo; da rendere privato prima di passare a soldi veri).

## Cosa fa
- Analizza ETF, crypto (Bitcoin, Ethereum) e azioni (Apple, Microsoft, Google, Amazon): sceglie in base al punteggio
  del momento (trend, volatilità, RSI) e resta fermo se non è convinto. A parità di punteggio vince l'asset meno volatile.
- Soglie per categoria: ETF stop-loss -10% / take-profit +15%; crypto/azioni -20% / +30%.
- Tetto 50% su crypto/azioni insieme, che si applica solo se in portafoglio c'è già un'altra posizione
  (interruttore `TETTO_ANCHE_CON_UNA_POSIZIONE` in `config.py`).
- Cambio posizione solo se l'alternativa è nettamente migliore E il guadagno copre le commissioni stimate.
- Posizioni multiple proposte a 150€ (2ª) e 400€ (3ª), sempre con conferma; salvadanaio; auto-valutazione; modalità difensiva.
- **Mai prezzi inventati in produzione**: se i dati reali mancano, il ciclo si ferma senza salvare nulla.

## Cicli (orari UTC stagionali: marzo-ottobre / novembre-febbraio)
| Ciclo | Script | Quando | Cosa fa |
|---|---|---|---|
| Principale | `run_ciclo.py` | 1 volta/giorno dopo Wall Street | Analisi completa, nuove posizioni, proposte |
| Sicurezza | `run_sicurezza.py` | 3 volte/giorno | Solo crypto/azioni: stop-loss, take-profit, cambio. Non apre mai posizioni |
| Backtest | `main.py` / workflow "backtest" | A mano | Rifà girare le regole sulla storia vera, con commissioni e confronto col solo VWCE.DE |

## La pagina
Saldo e variazione di oggi · controlli fatti oggi (X/4) · grafico e cronologia (10 giorni) · posizioni con categoria e variazione ·
barra del tetto di rischio · **"Cosa sta valutando Salvabot"** (punteggio di ogni candidato e motivo per cui resta fermo) ·
ultimi 4 controlli di sicurezza · notifiche con bottoni · prossimi passi · impostazioni.

## File
`config.py` parametri · `data_provider.py` prezzi (modalità solo-dati-reali) · `scoring.py` punteggi · `decision_engine.py` decisioni ·
`portfolio.py` saldo/storico · `state_store.py`/`settings_store.py` salvataggi · `notifications.py` notifiche ·
`self_evaluation.py` proposte di modifica · `run_ciclo.py`/`run_sicurezza.py` i due cicli · `genera_pagina.py` pagina ·
`gestisci_conferma.py` bottoni · `simulator.py`/`main.py` backtest · `.github/workflows/` (principale, sicurezza, conferme, backtest).

## Note da ricordare
- Rendere **privato** il repository prima dei soldi veri.
- Evitare che una proposta già rifiutata (es. salvadanaio) venga riproposta ogni giorno se il saldo resta sopra soglia.
- Cambio ora legale/solare approssimato per mese (scarto possibile di un'ora per 1-2 settimane l'anno).
- Rivedere ogni tanto `PANIERE_RISCHIOSO`; rivedere il tetto 50% quando si apre una nuova posizione.
- Gli orari mostrati sulla pagina sono in UTC. GitHub può ritardare o saltare un'esecuzione: il contatore può non arrivare a 4/4.
- Il backtest simula un passaggio al giorno (non i controlli intraday) e sottrae le commissioni stimate a fine periodo.

Software sperimentale: nessun rendimento è garantito. Non è consulenza finanziaria.

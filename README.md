# Salvabot

Bot di investimento paziente ("stile tartaruga"), in **demo** (nessun soldo vero, nessun broker collegato).
Gira da solo su GitHub Actions e si controlla da una pagina web, anche da smartphone.

## Cosa fa

- Analizza un paniere di **ETF, crypto (Bitcoin, Ethereum) e azioni (Apple, Microsoft, Google, Amazon)**
  e sceglie in base al punteggio del momento (trend, volatilità, RSI), restando fermo se non è convinto.
- **Soglie diverse per categoria**: ETF stop-loss -10% / take-profit +15%; crypto/azioni -20% / +30%.
- **Tetto del 50%** su crypto/azioni insieme (si applica quando in portafoglio c'è già un'altra posizione;
  vedi `TETTO_ANCHE_CON_UNA_POSIZIONE` in `config.py`).
- **Cambio posizione** se trova un'alternativa nettamente migliore, ma solo se il guadagno copre le
  commissioni stimate del cambio.
- **Posizioni multiple** proposte a soglia (150€ per la 2ª, 400€ per la 3ª), sempre con la tua conferma.
- **Salvadanaio**, **auto-valutazione** (propone modifiche, non le applica mai da sola), **modalità difensiva** sui crolli.

## Due cicli

| Ciclo | Script | Quando (UTC, stagionale) | Cosa fa |
|---|---|---|---|
| Principale | `run_ciclo.py` | 1 volta al giorno, dopo la chiusura di Wall Street | Analisi completa, nuove posizioni, proposte |
| Sicurezza | `run_sicurezza.py` | 3 volte al giorno | Solo crypto/azioni: stop-loss, take-profit, cambio. **Non apre mai nuove posizioni** |

Insieme fanno i "4 controlli al giorno" mostrati sulla pagina. Gli orari seguono l'ora legale con due
righe per mese (marzo-ottobre / novembre-febbraio): per 1-2 settimane l'anno, a cavallo del cambio ora,
può esserci uno scarto di un'ora.

## File

| File | Cosa fa |
|---|---|
| `config.py` | Tutti i parametri (soglie, paniere, tetto, categorie) |
| `data_provider.py` | Scarica i prezzi (yfinance); dati sintetici se offline. Scarta i prezzi mancanti |
| `scoring.py` | Volatilità, drawdown, trend, RSI (soglia di volatilità per categoria) |
| `decision_engine.py` | Decisioni, stop-loss/take-profit per categoria, cambio, tetto, modalità difensiva |
| `portfolio.py` | Saldo, salvadanaio, storico (10 giorni), ultimi 4 controlli, contatore giornaliero |
| `state_store.py` / `settings_store.py` | Salvataggio di stato e impostazioni (compatibile con i file vecchi) |
| `notifications.py` | Coda notifiche (una sola per tipo, aggiornata se si ripresenta) |
| `self_evaluation.py` | Propone modifiche ai parametri se nota pattern anomali |
| `run_ciclo.py` / `run_sicurezza.py` | I due cicli |
| `genera_pagina.py` | Genera `docs/index.html` |
| `gestisci_conferma.py` | Applica le scelte dei bottoni "Conferma"/"Non ora" |
| `simulator.py` / `main.py` | Backtest su dati storici |
| `.github/workflows/` | `salvabot.yml` (principale), `sicurezza.yml` (sicurezza), `gestisci_conferma.yml` (bottoni) |

## Aggiornare un repository già attivo

1. Sostituisci i file `.py` (sono tutti compatibili con lo stato già salvato: non serve cancellare nulla).
2. Sostituisci `.github/workflows/salvabot.yml` e `gestisci_conferma.yml`, e **crea** `.github/workflows/sicurezza.yml`
   (su GitHub: *Add file → Create new file*, nome `.github/workflows/sicurezza.yml`).
3. Verifica che in `config.py` `GITHUB_REPO` sia `"GitAntonio78/salvabot"`.
4. *Actions* → lancia a mano **"Salvabot - ciclo giornaliero"** e poi **"Salvabot - controllo di sicurezza"**.

## Da ricordare (note in sospeso)

- Rendere **privato** il repository prima di passare a soldi veri.
- Evitare che una proposta già rifiutata venga riproposta ogni giorno se il saldo resta sopra soglia.
- Affinare il cambio ora legale/solare (oggi approssimato per mese).
- Rivedere ogni tanto la lista di crypto/azioni (`PANIERE_RISCHIOSO` in `config.py`).
- Gli orari mostrati sulla pagina sono in UTC (ora del server GitHub).

Software sperimentale: nessun rendimento è garantito. Non è consulenza finanziaria.

# Salvabot — motore decisionale (versione demo)

Questa è la prima versione funzionante del "cervello" di Salvabot: analizza
un paniere di ETF, decide se investire o aspettare, e gestisce automaticamente
stop-loss e take-profit. È pensata per girare in **demo**, senza toccare soldi
veri e senza bisogno di un broker collegato.

## Due modi di far girare Salvabot

- **`main.py`** — demo su dati storici (backtest): utile per *testare* come si sarebbe comportata la strategia nel passato, non salva nulla tra un'esecuzione e l'altra.
- **`run_ciclo.py`** — esegue **un singolo ciclo operativo** con i dati più recenti, **salvando lo stato** (saldo, posizioni, salvadanaio) su file. Lanciandolo di nuovo, riparte esattamente da dove aveva lasciato. È questo il file pensato per essere eseguito periodicamente (es. una volta al giorno) una volta che sarà collegato a un server.

```bash
python3 run_ciclo.py --saldo 30
python3 run_ciclo.py   # lanci successivi: ricarica lo stato salvato automaticamente
```

Lo stato viene scritto in `stato_salvabot.json` (cancellalo se vuoi ripartire da zero).

## Come avviarla (demo su storico)

```bash
pip install -r requirements.txt
python3 main.py
```

Parametri opzionali:

```bash
python3 main.py --saldo 50 --cautela prudente --giorni 600
```

- `--saldo`: capitale di partenza della demo (default 30)
- `--cautela`: `prudente` / `equilibrato` / `dinamico` — quanti indicatori su 3
  devono essere favorevoli prima che Salvabot decida di investire
- `--giorni`: quanti giorni di storico usare per la simulazione

## Dati reali o sintetici?

Lo script prova prima a scaricare dati veri con `yfinance`. Se non c'è
connessione a internet (come in questo ambiente di sviluppo) o il pacchetto
non è installato, usa automaticamente dati sintetici generati con un random
walk, così puoi comunque vedere e testare tutta la logica del bot offline.
Il risultato indica sempre se ha usato dati reali o sintetici.

**Importante**: con i dati sintetici puoi verificare che la *logica* funzioni
(decisioni, stop-loss, pazienza), ma i numeri di rendimento non hanno alcun
significato reale — vanno letti solo con dati veri, con una connessione
internet attiva.

## Struttura dei file

| File | Cosa fa |
|---|---|
| `config.py` | Tutti i parametri modificabili (stop-loss, take-profit, soglie, panieri per fascia di saldo) |
| `data_provider.py` | Scarica i dati di mercato (yfinance) o li genera sinteticamente |
| `scoring.py` | Calcola volatilità, drawdown, trend, RSI per ogni ETF |
| `decision_engine.py` | Decide investi/aspetta/vendi, applica stop-loss e modalità difensiva |
| `portfolio.py` | Portafoglio virtuale: saldo composto, salvadanaio, trend di crescita/calo |
| `state_store.py` | Salva/ricarica lo stato completo di Salvabot su file, tra un'esecuzione e l'altra |
| `settings_store.py` | Salva/ricarica le impostazioni modificabili (stop-loss, take-profit, cautela), separate dai default |
| `notifications.py` | Coda persistente di notifiche (proposte, allarmi) — pronta per essere letta da una futura app |
| `self_evaluation.py` | Analizza i pattern recenti e propone modifiche; se confermate, le salva tramite `settings_store` |
| `simulator.py` | Fa girare tutto ciclo per ciclo su una serie storica (per test/backtest) |
| `run_ciclo.py` | Esegue un singolo ciclo operativo reale: carica impostazioni e stato, decide, salva, invia notifiche |
| `genera_pagina.py` | Genera `docs/index.html`: una pagina web semplice, leggibile da telefono, con saldo/salvadanaio/notifiche |
| `.github/workflows/salvabot.yml` | Il workflow che fa girare tutto da solo, ogni giorno, senza bisogno del tuo PC acceso |
| `main.py` | Punto d'ingresso a riga di comando per la demo su storico |

## Come attivare l'esecuzione automatica (gratis, senza server)

1. Crea un account GitHub (gratuito) se non ne hai già uno, e crea un nuovo repository (può essere privato)
2. Carica tutti questi file nel repository (via web, oppure con `git push` se hai già dimestichezza)
3. Vai su **Settings → Actions → General** del repository e assicurati che sia permesso "Read and write permissions" per il workflow (serve per salvare stato/pagina aggiornati automaticamente)
4. Vai su **Settings → Pages**, e imposta la pubblicazione dalla cartella `/docs` sul branch principale — otterrai un link tipo `https://tuonome.github.io/tuorepo/`, apribile da qualsiasi browser, anche da telefono
5. Da quel momento, ogni giorno alle 07:00 UTC (impostabile modificando l'orario nel file `.yml`), Salvabot gira da solo e aggiorna la pagina

Puoi anche lanciarlo manualmente subito, senza aspettare l'orario programmato: dalla scheda **Actions** del repository, seleziona il workflow "Salvabot - ciclo giornaliero" e premi "Run workflow".

## Il motore è completo

Con questo, il "cervello" di Salvabot copre tutto quello definito nel progetto: analisi/scoring, pazienza in ingresso, stop-loss/take-profit, modalità difensiva su crash, capitale composto, paniere a scalini per saldo, salvataggio persistente di stato e impostazioni, auto-valutazione con proposte confermabili, e una coda di notifiche reale.

## Prossime fasi (fuori dal motore)

1. **Server** — far girare `run_ciclo.py` in automatico ogni giorno (es. cron job) su una macchina sempre accesa
2. **App** — l'interfaccia (mockup già progettati) che legge stato/notifiche e permette di confermare le proposte, accessibile anche da smartphone
3. **Collegamento al broker** (Directa) per l'esecuzione reale, quando si deciderà di uscire dalla demo

## Nota importante

Questo è software sperimentale che, in una fase futura, potrebbe muovere
denaro reale. Nessun rendimento è garantito. Va sempre testato a lungo in
demo prima di qualsiasi collegamento a un conto reale.

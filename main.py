"""
Backtest di Salvabot da riga di comando (o dal workflow "Salvabot - backtest su dati reali").

Esempi:
    python3 main.py
    python3 main.py --giorni 1100 --posizioni 1 --cautela equilibrato
    python3 main.py --solo-dati-reali        # si rifiuta di girare su prezzi inventati
"""

import argparse
import sys

import config
from simulator import esegui_demo


def stampa_report(r: dict) -> None:
    m = r["metriche"]
    print("BACKTEST DI SALVABOT")
    print(f"Dati: {'REALI' if m['dati_reali_usati'] else 'SIMULATI (nessun valore reale: solo per prova tecnica)'}")
    if m["ticker_non_reali"]:
        print(f"  non reali: {', '.join(m['ticker_non_reali'])}")
    print(f"Periodo: {m['periodo_inizio']} -> {m['periodo_fine']} ({m['giorni_simulati']} giorni di borsa)")
    print(f"Capitale di partenza: {m['saldo_iniziale']:.2f} EUR\n")

    print("RISULTATO (commissioni stimate comprese)")
    print(f"  Salvabot:           {m['saldo_finale_netto']:.2f} EUR  ({m['rendimento_netto_pct']:+.2f}%)")
    print(f"  Solo VWCE.DE fermo: {m['benchmark_netto']:.2f} EUR  ({m['benchmark_rendimento_netto_pct']:+.2f}%)")
    diff = m["saldo_finale_netto"] - m["benchmark_netto"]
    print(f"  Differenza: {diff:+.2f} EUR a favore di {'Salvabot' if diff >= 0 else 'VWCE.DE fermo'}\n")

    print("RISCHIO")
    print(f"  Peggior calo dal massimo: Salvabot {m['drawdown_max_pct']}% | VWCE.DE fermo {m['benchmark_drawdown_max_pct']}%\n")

    print("COSA HA FATTO")
    print(f"  Operazioni: {m['n_operazioni']} (commissioni stimate {m['commissioni_stimate']:.2f} EUR)")
    a = m["acquisti_per_categoria"]
    print(f"  Acquisti: {a['ETF']} ETF, {a['Crypto']} crypto, {a['Azione']} azioni")
    print(f"  Stop-loss: {m['stop_loss']} | Take-profit: {m['take_profit']} | Cambi: {m['cambi']}")
    g = m["giorni_per_categoria"]
    liquidita = g["Liquidita'"]
    print(f"  Giorni in: ETF {g['ETF']} | Crypto {g['Crypto']} | Azioni {g['Azione']} | liquidita' {liquidita}\n")

    print("OPERAZIONI")
    for riga in r["log"]:
        print("  " + riga)
    print("\nNOTA: simulazione a un passaggio al giorno (i controlli intraday non sono simulati). "
          "Il passato non garantisce nulla sul futuro.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Salvabot - backtest storico")
    parser.add_argument("--saldo", type=float, default=config.SALDO_INIZIALE_DEFAULT)
    parser.add_argument("--cautela", choices=list(config.LIVELLI_CAUTELA), default=config.CAUTELA_DEFAULT)
    parser.add_argument("--giorni", type=int, default=1100, help="giorni di calendario di storia da scaricare")
    parser.add_argument("--posizioni", type=int, default=1, help="quante posizioni insieme")
    parser.add_argument("--solo-dati-reali", action="store_true", help="annulla il backtest se i dati non sono reali")
    args = parser.parse_args()

    try:
        r = esegui_demo(args.saldo, args.cautela, args.giorni, args.posizioni, richiedi_dati_reali=args.solo_dati_reali)
    except RuntimeError as errore:
        print(f"ERRORE: {errore}")
        return 1
    stampa_report(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())

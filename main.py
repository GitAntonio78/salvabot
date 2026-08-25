"""
Punto d'ingresso di Salvabot (versione demo, riga di comando).

Esempi:
    python3 main.py
    python3 main.py --saldo 50 --cautela prudente --giorni 600
"""

import argparse

import config
from simulator import esegui_demo


def main():
    parser = argparse.ArgumentParser(description="Salvabot - demo del motore decisionale")
    parser.add_argument("--saldo", type=float, default=config.SALDO_INIZIALE_DEFAULT, help="Saldo di partenza in euro")
    parser.add_argument(
        "--cautela",
        choices=list(config.LIVELLI_CAUTELA.keys()),
        default=config.CAUTELA_DEFAULT,
        help="Quanto essere cauto: prudente, equilibrato o dinamico",
    )
    parser.add_argument("--giorni", type=int, default=400, help="Giorni di storico su cui far girare la demo")
    args = parser.parse_args()

    risultato = esegui_demo(saldo_iniziale=args.saldo, cautela=args.cautela, giorni_storico=args.giorni)

    print(f"\nSalvabot - demo (dati {'reali' if risultato['metriche']['dati_reali_usati'] else 'sintetici, nessuna connessione trovata'})\n")
    print("--- Log delle attività ---")
    for riga in risultato["log"]:
        print(riga)

    print("\n--- Risultato finale ---")
    m = risultato["metriche"]
    print(f"Saldo iniziale: {m['saldo_iniziale']:.2f} EUR")
    print(f"Saldo finale:   {m['saldo_finale']:.2f} EUR")
    print(f"Rendimento:     {m['rendimento_pct']:.2f}%")
    print(f"Trend attuale:  {m['trend_attuale']} da {m['giorni_di_trend']} cicli")
    print(f"Cicli analizzati: {m['cicli_totali']}")


if __name__ == "__main__":
    main()

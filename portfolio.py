"""
Portafoglio virtuale (demo) e logiche di "maturità del saldo":
proposta di salvadanaio e proposta di espansione a crypto/azioni.

Nessuna soglia fissa: sono valori di configurazione (config.py) da
affinare, e in entrambi i casi Salvabot PROPONE, non impone.
"""

from dataclasses import dataclass, field

import config


@dataclass
class Portafoglio:
    saldo_investito: float
    salvadanaio: float = 0.0
    storico_saldo: list[float] = field(default_factory=list)
    storico_eventi: list[dict] = field(default_factory=list)

    def registra_evento(self, data: str, tipo: str) -> None:
        """
        Registra un evento tipizzato (per l'auto-valutazione).
        Tipi usati: 'investito', 'attesa', 'stop_loss', 'take_profit', 'difensiva'.
        """
        self.storico_eventi.append({"data": data, "tipo": tipo})

    def saldo_totale(self) -> float:
        return self.saldo_investito + self.salvadanaio

    def registra_saldo_giornaliero(self, saldo_operativo: float) -> None:
        """Da chiamare ogni ciclo per tenere lo storico (serve per 'in crescita da N giorni')."""
        self.storico_saldo.append(saldo_operativo)

    def giorni_di_trend(self) -> tuple[str, int]:
        """Restituisce ('crescita'|'calo'|'stabile', numero di giorni consecutivi)."""
        if len(self.storico_saldo) < 2:
            return "stabile", 0

        direzione_corrente = None
        giorni = 0
        for i in range(len(self.storico_saldo) - 1, 0, -1):
            variazione = self.storico_saldo[i] - self.storico_saldo[i - 1]
            direzione = "crescita" if variazione > 0 else ("calo" if variazione < 0 else "stabile")
            if direzione_corrente is None:
                direzione_corrente = direzione
            if direzione != direzione_corrente:
                break
            giorni += 1
        return direzione_corrente or "stabile", giorni

    def puo_proporre_salvadanaio(self) -> bool:
        return self.saldo_investito >= config.SOGLIA_PROPOSTA_SALVADANAIO

    def puo_proporre_espansione(self) -> bool:
        return self.saldo_investito >= config.SOGLIA_PROPOSTA_ESPANSIONE

    def applica_scelta_salvadanaio(self, quanto_accantonare: float) -> None:
        """L'utente conferma quanto spostare nel salvadanaio: il resto continua a lavorare."""
        quanto_accantonare = max(0.0, min(quanto_accantonare, self.saldo_investito))
        self.salvadanaio += quanto_accantonare
        self.saldo_investito -= quanto_accantonare

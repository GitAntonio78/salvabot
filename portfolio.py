"""
Portafoglio virtuale (demo), logiche di "maturità del saldo" (salvadanaio,
nuove posizioni), contatore dei controlli giornalieri e cronologia del
ciclo di sicurezza su crypto/azioni.

Nessuna soglia fissa dove non serve: sono valori di configurazione
(config.py) da affinare, e Salvabot PROPONE, non impone.
"""

from dataclasses import dataclass, field

import config


@dataclass
class Portafoglio:
    saldo_investito: float
    salvadanaio: float = 0.0
    storico_saldo: list[float] = field(default_factory=list)
    storico_eventi: list[dict] = field(default_factory=list)
    storico_punti: list[dict] = field(default_factory=list)  # ultimi 10 {data_ora, saldo}, per il grafico
    storico_controlli_sicurezza: list[dict] = field(default_factory=list)  # ultimi N {data_ora, esito}
    giorno_contatore_controlli: str = ""   # ultimo giorno in cui e' girato un ciclo (qualsiasi)
    controlli_oggi: int = 0                # quanti cicli (principale o sicurezza) sono girati oggi

    def registra_evento(self, data: str, tipo: str) -> None:
        """
        Registra un evento tipizzato (per l'auto-valutazione).
        Tipi usati: 'investito', 'attesa', 'stop_loss', 'take_profit', 'difensiva', 'switch'.
        """
        self.storico_eventi.append({"data": data, "tipo": tipo})

    def saldo_totale(self) -> float:
        return self.saldo_investito + self.salvadanaio

    def registra_saldo_giornaliero(self, saldo_operativo: float) -> None:
        """Da chiamare ogni ciclo per tenere lo storico (serve per 'in crescita da N giorni')."""
        self.storico_saldo.append(saldo_operativo)

    def registra_punto(self, data_ora: str, saldo: float, evento: bool = False) -> None:
        """
        Aggiunge un punto per il grafico (data/ora + saldo di quel ciclo).
        Un solo punto per giorno: se Salvabot gira piu' volte nello stesso
        giorno, aggiorna il punto di oggi invece di aggiungerne uno nuovo -
        cosi' i 10 punti restano sempre 10 giorni reali, non 10 passaggi.
        'evento' segnala che quel giorno e' successo qualcosa di rilevante
        (stop-loss, take-profit, cambio, nuova apertura): se un lancio
        successivo dello stesso giorno aggiorna il punto, il segnale NON si perde.
        Tiene solo gli ultimi 10 giorni: il più vecchio scompare quando ne arriva uno nuovo.
        """
        data_di_oggi = data_ora.split(" ")[0]  # "28/08 17:47" -> "28/08"
        punto = {"data_ora": data_ora, "saldo": round(saldo, 2), "evento": evento}
        if self.storico_punti and self.storico_punti[-1]["data_ora"].split(" ")[0] == data_di_oggi:
            punto["evento"] = evento or bool(self.storico_punti[-1].get("evento", False))
            self.storico_punti[-1] = punto
        else:
            self.storico_punti.append(punto)
        self.storico_punti = self.storico_punti[-10:]

    def registra_controllo_giornata(self, data_di_oggi: str) -> None:
        """
        Conta quanti cicli (principale o di sicurezza) sono girati OGGI.
        Si azzera da solo al cambio di giorno. Usato per mostrare "X/4 controlli".
        """
        if data_di_oggi != self.giorno_contatore_controlli:
            self.giorno_contatore_controlli = data_di_oggi
            self.controlli_oggi = 1
        else:
            self.controlli_oggi += 1

    def registra_controllo_sicurezza(self, data_ora: str, esito: str) -> None:
        """
        Aggiunge un controllo alla finestra a scorrimento (sempre gli ultimi
        FINESTRA_CONTROLLI_SICUREZZA, non per giorno - a differenza del grafico).
        """
        self.storico_controlli_sicurezza.append({"data_ora": data_ora, "esito": esito})
        self.storico_controlli_sicurezza = self.storico_controlli_sicurezza[-config.FINESTRA_CONTROLLI_SICUREZZA:]

    def giorni_di_trend(self) -> tuple[str, int]:
        """
        Restituisce ('crescita'|'calo'|'stabile', numero di giorni consecutivi).
        Si basa sui punti GIORNALIERI (uno per giorno, gli stessi del grafico), non
        su ogni singolo controllo: con 4 controlli al giorno, il rumore tra un
        controllo e l'altro farebbe contraddire il badge con la variazione del giorno.
        """
        valori = [p["saldo"] for p in self.storico_punti if p["saldo"] == p["saldo"]]
        if len(valori) < 2:
            valori = [v for v in self.storico_saldo if v == v]  # stati vecchi senza punti giornalieri
        if len(valori) < 2:
            return "stabile", 0

        direzione_corrente = None
        giorni = 0
        for i in range(len(valori) - 1, 0, -1):
            variazione = valori[i] - valori[i - 1]
            direzione = "crescita" if variazione > 0 else ("calo" if variazione < 0 else "stabile")
            if direzione_corrente is None:
                direzione_corrente = direzione
            if direzione != direzione_corrente:
                break
            giorni += 1
        return direzione_corrente or "stabile", giorni

    def puo_proporre_salvadanaio(self) -> bool:
        return self.saldo_investito >= config.SOGLIA_PROPOSTA_SALVADANAIO

    def puo_proporre_nuova_posizione(self, posizioni_consentite: int) -> bool:
        """
        True se il saldo ha raggiunto la soglia per proporre una posizione
        aggiuntiva rispetto a quelle gia' consentite. Non propone piu' nulla
        una volta superate le soglie definite in config (si può estendere).
        """
        indice = posizioni_consentite - 1  # 1->2 usa soglia[0], 2->3 usa soglia[1], ecc.
        if indice < 0 or indice >= len(config.SOGLIE_POSIZIONI_AGGIUNTIVE):
            return False
        return self.saldo_investito >= config.SOGLIE_POSIZIONI_AGGIUNTIVE[indice]

    def applica_scelta_salvadanaio(self, quanto_accantonare: float) -> None:
        """L'utente conferma quanto spostare nel salvadanaio: il resto continua a lavorare."""
        quanto_accantonare = max(0.0, min(quanto_accantonare, self.saldo_investito))
        self.salvadanaio += quanto_accantonare
        self.saldo_investito -= quanto_accantonare

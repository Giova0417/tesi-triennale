import traci

# Costanti delle fasi
NS_GREEN = 0
NS_YELLOW = 1
ALL_RED_1 = 2
EW_GREEN = 3
EW_YELLOW = 4
ALL_RED_2 = 5

PHASE_NAMES = {
    NS_GREEN: "NS_GREEN",
    NS_YELLOW: "NS_YELLOW",
    ALL_RED_1: "ALL_RED_1",
    EW_GREEN: "EW_GREEN",
    EW_YELLOW: "EW_YELLOW",
    ALL_RED_2: "ALL_RED_2",
}

# Sequenze fisse di transizione
NS_TO_EW = [NS_YELLOW, ALL_RED_1, EW_GREEN]
EW_TO_NS = [EW_YELLOW, ALL_RED_2, NS_GREEN]

class SafetySupervisor:
    """
    Gestisce la sicurezza stradale, i vincoli temporali e le transizioni 
    indipendentemente dalle decisioni dell'LLM.
    """
    def __init__(
        self, 
        min_green: int = 10, 
        max_green: int = 60, 
        yellow_time: int = 3, 
        all_red_time: int = 2
    ) -> None:
        # Parametri configurabili (richiesti dall'assistente)
        self.MIN_GREEN = min_green
        self.MAX_GREEN = max_green
        self.YELLOW_TIME = yellow_time
        self.ALL_RED_TIME = all_red_time

        self.current_phase: int = NS_GREEN
        self.phase_start_time: int = 0
        self.sim_time: int = 0

        self._transition_queue: list[int] = []
        self._pending_phase: int | None = None

    def tick(self, sim_time: int) -> None:
        """Avanza lo stato interno del Supervisor."""
        self.sim_time = sim_time

        # Se non stiamo cambiando fase, non c'è nulla da aggiornare
        if not self._transition_queue:
            return

        elapsed = self.sim_time - self.phase_start_time
        duration = self._phase_duration(self.current_phase)

        # Se il tempo della fase intermedia (giallo o rosso) è finito, passa alla successiva
        if elapsed >= duration:
            self._pending_phase = self._transition_queue.pop(0)

    def _phase_duration(self, phase: int) -> int:
        if phase in (NS_YELLOW, EW_YELLOW):
            return self.YELLOW_TIME
        if phase in (ALL_RED_1, ALL_RED_2):
            return self.ALL_RED_TIME
        return self.MAX_GREEN 

    def get_allowed_actions(self) -> list[str]:
        """Restituisce le azioni legalmente permesse in base allo stato attuale."""
        elapsed_green = self.sim_time - self.phase_start_time

        # Se siamo nel mezzo di un cambio fase (Giallo o Rosso), l'LLM non può fare nulla
        if self.current_phase not in (NS_GREEN, EW_GREEN):
            return ["HOLD"]

        # Se il Verde Minimo non è ancora trascorso, non possiamo cambiare
        if elapsed_green < self.MIN_GREEN:
            return ["HOLD"]

        # Se siamo in Verde stabile e il MinGreen è passato, si può cambiare
        if self.current_phase == NS_GREEN:
            return ["HOLD", "REQUEST_EW"]
        
        return ["HOLD", "REQUEST_NS"]

    def request(
        self, requested_action: str, opposite_queue: int
    ) -> tuple[str, str]:
        """
        Riceve l'azione dall'LLM (o dal Fallback) e decide se applicarla.
        Ritorna: (Azione Eseguita, Motivo)
        """
        elapsed_green = self.sim_time - self.phase_start_time

        # 1. Sicurezza Fisica: Ignoriamo l'LLM durante le transizioni in corso
        if self.current_phase not in (NS_GREEN, EW_GREEN):
            return "HOLD", "TRANSITION_IN_PROGRESS"

        # 2. Anti-Starvation (Migliorato come richiesto dall'assistente):
        # Forza il cambio SOLO se c'è coda dall'altra parte.
        if elapsed_green >= self.MAX_GREEN and opposite_queue > 0:
            self._start_switch()
            return "SWITCH", "MAX_GREEN_FORCED"

        # 3. Mantenimento volontario dello stato
        if requested_action == "HOLD":
            return "HOLD", "LLM_HOLD"

        # 4. Validazione dell'azione rispetto alla fase corrente
        wants_switch = (
            (requested_action == "REQUEST_EW" and self.current_phase == NS_GREEN) or 
            (requested_action == "REQUEST_NS" and self.current_phase == EW_GREEN)
        )

        if not wants_switch:
            return "HOLD", "INVALID_ACTION_FOR_PHASE"

        # 5. Vincolo di Verde Minimo
        if elapsed_green < self.MIN_GREEN:
            return "HOLD", "MIN_GREEN_NOT_ELAPSED"

        # 6. Azione sicura: cambiamo fase!
        self._start_switch()
        return "SWITCH", "LLM_APPROVED"

    def _start_switch(self) -> None:
        """Innesca la sequenza di transizione sicura."""
        if self._transition_queue:
            return

        if self.current_phase == NS_GREEN:
            self._transition_queue = list(NS_TO_EW)
        elif self.current_phase == EW_GREEN:
            self._transition_queue = list(EW_TO_NS)

        self._pending_phase = self._transition_queue.pop(0)

    def apply_traci(self, tls_id: str) -> None:
        """Applica la fase decisa fisicamente su SUMO via TraCI."""
        if self._pending_phase is None:
            return

        traci.trafficlight.setPhase(tls_id, self._pending_phase)
        self.current_phase = self._pending_phase
        self.phase_start_time = self.sim_time
        self._pending_phase = None
NS_GREEN = 0
NS_YELLOW = 1
ALL_RED_1 = 2
EW_GREEN = 3
EW_YELLOW = 4
ALL_RED_2 = 5

class SafetySupervisor:
    MIN_GREEN_TIME = 10
    MAX_GREEN_TIME = 60  # <-- NUOVO: Vincolo Anti-Starvation
    YELLOW_TIME = 4
    RED_CLEARANCE_TIME = 2

    def get_safe_phase(self, current_phase: int, phase_elapsed: int, llm_action: str) -> int:
        # 1. Transizioni ineluttabili: Giallo
        if current_phase in (NS_YELLOW, EW_YELLOW):
            if phase_elapsed < self.YELLOW_TIME:
                return current_phase
            return ALL_RED_1 if current_phase == NS_YELLOW else ALL_RED_2

        # 2. Transizioni ineluttabili: Tutti Rossi di sicurezza
        if current_phase in (ALL_RED_1, ALL_RED_2):
            if phase_elapsed < self.RED_CLEARANCE_TIME:
                return current_phase
            return EW_GREEN if current_phase == ALL_RED_1 else NS_GREEN

        # 3. ANTI-STARVATION: Se l'IA si incanta, forza il cambio per sbloccare il traffico
        if phase_elapsed >= self.MAX_GREEN_TIME:
            if current_phase == NS_GREEN:
                return NS_YELLOW
            if current_phase == EW_GREEN:
                return EW_YELLOW

        # 4. Vincolo sul Verde Minimo
        if phase_elapsed < self.MIN_GREEN_TIME:
            return current_phase

        # 5. Fase stabile (Verde) -> Ascoltiamo l'IA
        if llm_action == "HOLD":
            return current_phase

        if current_phase == NS_GREEN and llm_action == "REQUEST_EW":
            return NS_YELLOW

        if current_phase == EW_GREEN and llm_action == "REQUEST_NS":
            return EW_YELLOW

        return current_phase
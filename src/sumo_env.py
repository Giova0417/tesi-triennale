import sys
import traci
import sumolib

from traffic_state import TrafficState

TLS_ID = "J0"
APPROACH_EDGES = ("N2J", "S2J", "E2J", "W2J")


class SumoEnvironment:
    """
    Wrapper attorno a TraCI: nasconde i dettagli di connessione al simulatore
    ed espone un'interfaccia pulita per Observer/FSM/Controller a monte.
    """

    def __init__(self, sumocfg_path: str, tls_id: str = TLS_ID, gui: bool = True) -> None:
        # LEGGE IL COMANDO DAL RUNNER: se c'è --nogui, spegne l'interfaccia grafica
        if "--nogui" in sys.argv:
            gui = False
            
        self.sumocfg_path = sumocfg_path
        self.tls_id = tls_id
        self.gui = gui

        self._phase_start_time: int = 0
        self._last_phase_id: str | None = None

    def start(self) -> None:
        binary = sumolib.checkBinary("sumo-gui" if self.gui else "sumo")
        traci.start([binary, "-c", self.sumocfg_path])

    def close(self) -> None:
        traci.close()

    def step(self) -> None:
        traci.simulationStep()

    def get_state(self) -> TrafficState:
        sim_time = int(traci.simulation.getTime())
        phase_id = traci.trafficlight.getPhaseName(self.tls_id)

        # il tempo trascorso in fase lo teniamo noi: TraCI non espone
        # direttamente "da quanto è attiva la fase corrente"
        if phase_id != self._last_phase_id:
            self._last_phase_id = phase_id
            self._phase_start_time = sim_time

        phase_elapsed = sim_time - self._phase_start_time

        queue_by_approach = {
            edge: traci.edge.getLastStepHaltingNumber(edge) for edge in APPROACH_EDGES
        }
        waiting_by_approach = {
            edge: traci.edge.getWaitingTime(edge) for edge in APPROACH_EDGES
        }

        return TrafficState(
            sim_time=sim_time,
            phase_id=phase_id,
            phase_elapsed=phase_elapsed,
            queue_by_approach=queue_by_approach,
            waiting_by_approach=waiting_by_approach,
        )

    def set_phase(self, phase_index: int) -> None:
        traci.trafficlight.setPhase(self.tls_id, phase_index)
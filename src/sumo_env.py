import sys
import traci
import sumolib
from typing import Optional

from traffic_state import TrafficState

TLS_ID = "J0"
APPROACH_EDGES = ("N2J", "S2J", "E2J", "W2J")

class SumoEnvironment:
    def __init__(self, sumocfg_path: str, tls_id: str = TLS_ID, gui: bool = True, seed: int = 42, scale: float = 1.0) -> None:
        if "--nogui" in sys.argv:
            gui = False
            
        self.sumocfg_path = sumocfg_path
        self.tls_id = tls_id
        self.gui = gui
        self.seed = seed
        self.scale = scale

        self._phase_start_time: int = 0
        self._last_phase_id: str | None = None

    def start(self, tripinfo_path: Optional[str] = None, emissions_path: Optional[str] = None) -> None:
        binary = sumolib.checkBinary("sumo-gui" if self.gui else "sumo")
        cmd = [
            binary, 
            "-c", self.sumocfg_path, 
            "--seed", str(self.seed), 
            "--scale", str(self.scale)
        ]
        
        if tripinfo_path:
            cmd.extend(["--tripinfo-output", tripinfo_path])
        if emissions_path:
            cmd.extend(["--emission-output", emissions_path])
            
        traci.start(cmd)

    def close(self) -> None:
        traci.close()

    def step(self) -> None:
        traci.simulationStep()

    def get_state(self) -> TrafficState:
        sim_time = int(traci.simulation.getTime())
        phase_id = traci.trafficlight.getPhaseName(self.tls_id)

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
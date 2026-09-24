from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

ActionId = Literal["HOLD", "REQUEST_NS", "REQUEST_EW"]

ReasonCode = Literal[
    "QUEUE_HIGH",
    "WAIT_HIGH",
    "STARVATION",
    "TREND_RISING",
    "BALANCED",
]

class LLMDecision(BaseModel):
    action_id: ActionId
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    explanation: str = Field(max_length=200)

    # REQUISITO RELATORE: Pydantic rigoroso, niente campi extra tollerati
    model_config = ConfigDict(extra='forbid')

class StateEncoder:
    """
    Traduce lo stato interno della simulazione in un dizionario JSON-ready
    da iniettare nel prompt.
    """
    @staticmethod
    def encode(
        state,
        allowed_actions: list[str]
    ) -> dict:
        q = state.queue_by_approach
        w = state.waiting_by_approach

        return {
            "sim_time": state.sim_time,
            "phase": state.phase_id,
            "elapsed_green": state.phase_elapsed,
            "queues": {
                "NS": q.get("N2J", 0) + q.get("S2J", 0),
                "EW": q.get("E2J", 0) + q.get("W2J", 0),
                "by_approach": q,
            },
            "waiting_time": {
                "NS": w.get("N2J", 0.0) + w.get("S2J", 0.0),
                "EW": w.get("E2J", 0.0) + w.get("W2J", 0.0),
                "by_approach": w,
            },
            "allowed_actions": allowed_actions,
        }
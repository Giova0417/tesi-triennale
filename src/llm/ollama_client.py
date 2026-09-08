import json

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from llm.schemas import LLMDecision

SYSTEM_PROMPT = """Sei il modulo decisionale di un sistema di controllo semaforico adattivo.

Il tuo ruolo è analizzare lo stato di un incrocio a 4 bracci (Nord-Sud / Est-Ovest)
e scegliere UNA macro-azione strategica. Non controlli direttamente le luci del
semaforo: la tua decisione viene validata e applicata da un Safety Supervisor
deterministico che può ignorarla se viola vincoli di sicurezza.

Devi rispondere ESCLUSIVAMENTE con un oggetto JSON con questa struttura esatta,
senza testo aggiuntivo prima o dopo:

{
  "action_id": "HOLD" | "REQUEST_NS" | "REQUEST_EW",
  "reason_codes": ["QUEUE_HIGH" | "WAIT_HIGH" | "STARVATION" | "TREND_RISING" | "BALANCED"],
  "explanation": "breve motivazione, max 200 caratteri"
}

Regole:
- action_id deve essere scelto SOLO tra i valori presenti nel campo "allowed_actions"
  dello stato che ricevi. Se un'azione non è nella lista, non puoi proporla.
- reason_codes deve contenere solo codici dalla whitelist indicata sopra.
- Non aggiungere campi extra, non aggiungere commenti, non aggiungere markdown.
"""


class OllamaClient:
    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def get_decision(self, state_dict: dict) -> LLMDecision:
        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(state_dict)},
            ],
        }

        # se la request fallisce (timeout, connessione rifiutata, 5xx...)
        # l'eccezione risale e tenacity fa scattare il retry
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        raw_content = response.json()["message"]["content"]

        # se il modello ha allucinato campi/valori fuori schema, model_validate_json
        # lancia ValidationError e tenacity riprova la chiamata da capo
        return LLMDecision.model_validate_json(raw_content)


if __name__ == "__main__":
    # Test a secco: simuliamo un incrocio con forte traffico sull'asse NS
    fake_state = {
        "sim_time": 120,
        "phase": "G_EW", # Il verde ce l'ha l'asse Est-Ovest
        "elapsed_green": 45,
        "queues": {"NS": 40, "EW": 2}, # 40 auto in attesa a Nord-Sud!
        "waiting_time": {"NS": 1200.0, "EW": 10.0},
        "trend": {"NS": "STABLE", "EW": "STABLE"},
        "allowed_actions": ["HOLD", "REQUEST_NS"]
    }
    
    print("Connessione a Ollama in corso... Attendi la decisione dell'IA.")
    # Se hai scaricato qwen2 invece di llama3.1, cambialo qui sotto
    client = OllamaClient(model="llama3.1") 
    
    try:
        decision = client.get_decision(fake_state)
        print("\n--- RISPOSTA DELL'IA ---")
        print(f"Azione Scelta: {decision.action_id}")
        print(f"Motivazioni: {decision.reason_codes}")
        print(f"Spiegazione: {decision.explanation}")
    except Exception as e:
        print(f"\nErrore durante il test: {e}")
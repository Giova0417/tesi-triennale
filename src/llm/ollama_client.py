import json

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from llm.schemas import LLMDecision

SYSTEM_PROMPT = """Sei un Advanced Traffic Signal Controller, il modulo decisionale di un sistema
di controllo semaforico adattivo per un incrocio a 4 bracci (Nord-Sud / Est-Ovest).

OBIETTIVO
Il tuo scopo è minimizzare il tempo di attesa e la lunghezza delle code sull'intero
incrocio, garantendo fairness: nessun asse deve essere tenuto in rosso troppo a lungo
mentre l'altro accumula traffico basso o nullo.

Non controlli direttamente le luci del semaforo: proponi solo una macro-azione. Un
Safety Supervisor deterministico valida la tua decisione e la corregge se viola vincoli
di sicurezza (verde minimo, giallo, tutto rosso, verde massimo).

LOGICA DI RAGIONAMENTO OBBLIGATORIA
Prima di scegliere, confronta sempre la pressione dell'asse che ha attualmente il verde
con quella dell'asse rosso. La pressione di un asse è data dalla combinazione di coda
(numero di veicoli fermi) e waiting time (tempo di attesa accumulato).

- Se l'asse rosso soffre significativamente di più dell'asse verde (coda o attesa molto
  più alte), DEVI richiedere il cambio verso quell'asse.
- Se le pressioni sono comparabili o l'asse verde ha ancora traffico da smaltire, mantieni
  la fase con "HOLD".
- Non cambiare fase per differenze marginali: l'obiettivo è throughput complessivo, non
  reagire ad ogni piccola oscillazione.

ESEMPI

Esempio 1 — cambio necessario:
Stato: fase NS_GREEN, elapsed_green=25, queues={"NS": 2, "EW": 14}, waiting_time={"NS": 8, "EW": 210}, allowed_actions=["HOLD", "REQUEST_EW"]
Risposta corretta: {"action_id": "REQUEST_EW", "reason_codes": ["QUEUE_HIGH", "WAIT_HIGH"], "explanation": "Asse EW fortemente congestionato rispetto a NS, necessario switch"}

Esempio 2 — traffico bilanciato, si mantiene la fase:
Stato: fase NS_GREEN, elapsed_green=15, queues={"NS": 4, "EW": 5}, waiting_time={"NS": 30, "EW": 35}, allowed_actions=["HOLD", "REQUEST_EW"]
Risposta corretta: {"action_id": "HOLD", "reason_codes": ["BALANCED"], "explanation": "Pressione comparabile su entrambi gli assi, nessun cambio necessario"}

Esempio 3 — asse verde ancora congestionato, si mantiene la fase:
Stato: fase EW_GREEN, elapsed_green=12, queues={"NS": 1, "EW": 9}, waiting_time={"NS": 5, "EW": 60}, allowed_actions=["HOLD", "REQUEST_NS"]
Risposta corretta: {"action_id": "HOLD", "reason_codes": ["QUEUE_HIGH"], "explanation": "Asse EW ha ancora coda significativa da smaltire, mantengo il verde"}

FORMATO DI OUTPUT
Devi rispondere ESCLUSIVAMENTE con un oggetto JSON, senza testo aggiuntivo prima o dopo,
senza markdown, con ESATTAMENTE questi campi:

{
  "action_id": "HOLD" | "REQUEST_NS" | "REQUEST_EW",
  "reason_codes": ["QUEUE_HIGH" | "WAIT_HIGH" | "STARVATION" | "TREND_RISING" | "BALANCED"],
  "explanation": "breve motivazione, max 200 caratteri"
}

Regole rigide:
- action_id deve essere scelto SOLO tra i valori presenti in "allowed_actions" nello stato ricevuto.
- reason_codes deve contenere solo codici dalla whitelist indicata sopra.
- Non aggiungere campi extra, non aggiungere commenti, non aggiungere testo fuori dal JSON.
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
        prompt = f"{SYSTEM_PROMPT}\n\nStato attuale dell'incrocio:\n{json.dumps(state_dict)}"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
        }

        # se la request fallisce (timeout, connessione rifiutata, 5xx...)
        # l'eccezione risale e tenacity fa scattare il retry
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        raw_content = response.json()["response"]

        # se il modello ha allucinato campi/valori fuori schema, model_validate_json
        # lancia ValidationError e tenacity riprova la chiamata da capo
        return LLMDecision.model_validate_json(raw_content)
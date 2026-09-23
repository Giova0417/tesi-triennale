# Controllo Semaforico Adattivo tramite LLM in SUMO

Prototipo di sistema di controllo semaforico gerarchico per un incrocio singolo a 4 bracci, in cui un Large Language Model (eseguito in locale tramite Ollama) propone decisioni strategiche di alto livello, mentre un Safety Supervisor deterministico ne valida e corregge l'esecuzione fisica sul simulatore SUMO.

L'LLM non controlla mai direttamente le luci del semaforo: sceglie solo tra macro-azioni ("HOLD", "REQUEST_NS", "REQUEST_EW"), che vengono poi tradotte in transizioni di fase sicure da una macchina a stati finita scritta in Python puro.

## Requisiti di sistema

- **Eclipse SUMO** installato e aggiunto alle variabili d'ambiente di sistema (variabile `SUMO_HOME` configurata correttamente)
- **Ollama** in esecuzione in locale, con un modello scaricato (es. `llama3.1`)
- **Python 3.10+**

## Installazione dipendenze

```bash
pip install traci sumolib requests tenacity pydantic pandas matplotlib
```

## Struttura del progetto

```text
.
├── scenarios/
│   └── synthetic_4arm/
│       ├── network.net.xml      # geometria della rete (nodi, edge, TLS)
│       ├── routes.rou.xml       # veicoli, flussi e rotte
│       └── scenario.sumocfg     # configurazione generale della simulazione
│
└── src/
    ├── main.py                  # entry point: orchestrazione del ciclo di simulazione
    ├── sumo_env.py              # interfaccia TraCI verso SUMO
    ├── safety_supervisor.py     # Safety Supervisor (FSM di sicurezza)
    ├── traffic_state.py         # data model dello stato dell'incrocio
    └── llm/
        ├── schemas.py           # validazione Pydantic delle decisioni dell'LLM
        └── ollama_client.py     # client HTTP verso Ollama
```

## Safety Supervisor

Il cuore del sistema di sicurezza è `safety_supervisor.py`. Si tratta di una macchina a stati finita deterministica a 6 fasi che riceve la macro-azione proposta dall'LLM e la applica solo se non viola i vincoli di sicurezza stradale:

- **Verde minimo:** nessuna transizione può essere avviata prima che sia trascorso il tempo minimo di verde configurato, indipendentemente da cosa richiede l'LLM.
- **Giallo vincolato:** una volta avviato il giallo, la sua durata è fissa e non può essere interrotta o prolungata dall'LLM.
- **Fase di clearance "Tutto Rosso":** prima di concedere il verde all'asse opposto, la FSM attraversa una fase intermedia in cui tutte le direzioni sono rosse, ineliminabile e non bypassabile da nessuna decisione esterna.
- **Vincolo Anti-Starvation (Max Green):** se l'LLM continua a proporre "HOLD" sullo stesso asse oltre una soglia massima di verde ("Target Fixation"), il Supervisor forza autonomamente lo sblocco dell'incrocio, avviando la transizione verso l'asse opposto indipendentemente dalla decisione del modello.

L'LLM propone, il Supervisor dispone: qualunque richiesta arrivi dal modello, se non rispetta questi vincoli temporali viene ignorata e sostituita con la fase sicura corrente.

## Istruzioni per l'uso

```bash
cd src
python main.py
```

Lo script avvia SUMO in modalità GUI, connette il client Ollama e fa girare la simulazione per 3600 step (1 ora simulata), stampando a schermo lo stato dell'incrocio, la decisione dell'LLM e la fase applicata ad ogni step.

## Raccolta dati

Ad ogni step della simulazione, la lunghezza delle code per asse (Nord-Sud ed Est-Ovest), la fase attiva del semaforo e la decisione presa dall'LLM vengono estratte in tempo reale e salvate riga per riga in `src/simulation_results.csv`. Questo file è pronto per essere importato direttamente in pandas/matplotlib per la generazione dei grafici di analisi presenti nella tesi.
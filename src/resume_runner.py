import subprocess
import os
from pathlib import Path

def main():
    print("Ripresa delle simulazioni interrotte...")
    
    # Esegue solo LLM con i seed 100 e 2024
    for seed in [100, 2024]:
        print(f"\n==================================================")
        print(f"Recupero esperimento: Policy=LLM | Seed={seed} | Traffic=medium")
        print(f"==================================================")
        
        env_vars = os.environ.copy()
        env_vars["TLS_POLICY"] = "llm"
        env_vars["SUMO_SEED"] = str(seed)
        env_vars["TRAFFIC_LEVEL"] = "medium"
        
        # Percorso di output
        csv_path = Path(__file__).parent.parent / "results" / "medium" / "llm" / f"seed_{seed}" / "simulation_results.csv"
        env_vars["CSV_OUTPUT_PATH"] = str(csv_path.resolve())

        # Lancia il main
        try:
            subprocess.run(["python", "main.py", "--nogui"], env=env_vars, check=True)
            print(f"Recupero llm-{seed} completato con successo.")
        except subprocess.CalledProcessError:
            print(f"ERRORE durante il recupero di llm-{seed}.")

if __name__ == "__main__":
    main()
import subprocess
import os
from pathlib import Path

def main():
    print("Ripresa delle simulazioni interrotte (Traffico HEAVY)...")
    
    # Lista esatta degli esperimenti falliti per disco pieno
    failed_experiments = [
        ("pressure", 777),
        ("pressure", 999),
        ("llm", 42),
        ("llm", 100),
        ("llm", 2024),
        ("llm", 777),
        ("llm", 999)
    ]
    
    for policy, seed in failed_experiments:
        print(f"\n==================================================")
        print(f"Recupero esperimento: Policy={policy.upper()} | Seed={seed} | Traffic=heavy")
        print(f"==================================================")
        
        env_vars = os.environ.copy()
        env_vars["TLS_POLICY"] = policy
        env_vars["SUMO_SEED"] = str(seed)
        env_vars["TRAFFIC_LEVEL"] = "heavy"
        
        # Percorso di output
        csv_path = Path(__file__).parent.parent / "results" / "heavy" / policy / f"seed_{seed}" / "simulation_results.csv"
        env_vars["CSV_OUTPUT_PATH"] = str(csv_path.resolve())

        try:
            subprocess.run(["python", "main.py", "--nogui"], env=env_vars, check=True)
            print(f"Recupero {policy}-{seed} completato con successo.")
        except subprocess.CalledProcessError:
            print(f"ERRORE durante il recupero di {policy}-{seed}.")

if __name__ == "__main__":
    main()
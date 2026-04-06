import subprocess
import json
import os
import sys

# Configuración de rutas (Ajusta si es necesario)
BASE_DIR = r'C:\Users\elmik\Downloads\DAI'
ROUTER_PATH = os.path.join(BASE_DIR, 'Router', 'Router.py')
PLANNER_PATH = os.path.join(BASE_DIR, 'Planner', 'Planner.py')
EXECUTOR_PATH = os.path.join(BASE_DIR, 'Executor', 'Executor.py')
VERIFIER_PATH = os.path.join(BASE_DIR, 'Verifier', 'Verifier.py')

# Rutas de datos
PIPELINE_JSON = os.path.join(BASE_DIR, 'Router', 'pipeline_entry.json')
VERIFIER_JSON = os.path.join(BASE_DIR, 'Verifier', 'verification_result.json')

# Import Router
sys.path.append(os.path.join(BASE_DIR, 'Router'))
from Router import router_node

def run_script(path):
    """Ejecuta un script de Python y espera a que termine."""
    try:
        result = subprocess.run(['python', path], capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    print("=== DAI: Desktop Artificial Intelligence Operativa ===")
    print("Esperando comandos del usuario...")

    # Initialize history
    if os.path.exists(PIPELINE_JSON):
        try:
            with open(PIPELINE_JSON, 'r') as f:
                history = json.load(f)
        except:
            history = []
    else:
        history = []

    while True:
        user_input = input("Enter your message (or 'quit' to exit): ")
        if user_input.lower() == 'quit':
            print("Cerrando DAI... Hasta luego.")
            break

        # Call Router
        entry = router_node(user_input)
        if 'error' in entry:
            print(f"[ERROR] Router error: {entry['error']}")
            continue

        # Append to history and save
        history.append(entry)
        with open(PIPELINE_JSON, 'w') as f:
            json.dump(history, f, indent=4)

        classification = entry.get('classification')

        if classification == 'Tarea':
            print(f"\n[SISTEMA] Tarea detectada: '{user_input}'")
            print("[SISTEMA] Iniciando Pipeline de Automatización...")

            # PASO: Planner
            print(" -> Generando plan...")
            success, output = run_script(PLANNER_PATH)
            if not success:
                print(f"[ERROR] Planner falló: {output}")
                continue

            # PASO: Executor
            print(" -> Ejecutando acciones...")
            success, output = run_script(EXECUTOR_PATH)
            if not success:
                print(f"[ERROR] Executor falló: {output}")
                continue

            # PASO: Verifier
            print(" -> Verificando resultado...")
            success, output = run_script(VERIFIER_PATH)
            if not success:
                print(f"[ERROR] Verifier falló: {output}")
                continue

            # Read Verifier result
            try:
                with open(VERIFIER_JSON, 'r') as f:
                    result = json.load(f)
                status = result.get('status', 'UNKNOWN')
                print(f"[SISTEMA] Resultado de la verificación: {status}")
            except Exception as e:
                print(f"[ERROR] No se pudo leer el resultado del Verifier: {e}")

            print("[SISTEMA] Ciclo de tarea finalizado.")
            print("[DAI]: ¡Tarea completada exitosamente! ¿En qué más puedo ayudarte?")
            print("-" * 30)
        
        elif classification == 'Chat':
            response = entry.get('response', 'No response generated')
            print(f"\n[DAI-Chat]: {response}")
            print("-" * 30)
        
        else:
            print(f"[SISTEMA] Clasificación desconocida: {classification}")

if __name__ == "__main__":
    main()
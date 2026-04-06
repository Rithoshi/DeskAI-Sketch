import json
import os
import time

# Rutas de tus archivos
JSON1_PATH = r'C:\Users\elmik\Downloads\DAI\Router\pipeline_entry.json'
JSON2_PATH = r'C:\Users\elmik\Downloads\DAI\Executor\execution_log.json'

def verify_task():
    print("--- [VERIFIER] Iniciando verificación de tarea ---")
    
    try:
        # 1. Leer Tarea Inicial (JSON1)
        with open(JSON1_PATH, 'r') as f1:
            data_input = json.load(f1)
            # Asumiendo que es una lista, tomar el último
            if isinstance(data_input, list) and data_input:
                original_task = data_input[-1]['input']
            elif isinstance(data_input, dict):
                original_task = data_input['input']
            else:
                original_task = "No task found"

        # 2. Leer Resultado del Executor (JSON2)
        with open(JSON2_PATH, 'r') as f2:
            execution_data = json.load(f2)
            # Tomamos el último log de ejecución
            last_run = execution_data[-1] 
            
        stdout = last_run.get('stdout', '')
        returncode = last_run.get('returncode', -1)
        attempts = last_run.get('plan', {}).get('attempts', 1)

        print(f"Tarea Original: {original_task}")
        print(f"Código de retorno: {returncode}")

        # 3. Lógica de Verificación
        # Criterio básico: Si el returncode es 0 y el critic pasó, es un buen inicio.
        # Podrías añadir una validación extra aquí (ej. buscar palabras clave en stdout)
        success_criteria = (returncode == 0)

        if success_criteria:
            print("--- [VERIFIER] RESULTADO: COMPLETADO ---")
            return "COMPLETADO"
        
        else:
            if attempts < 3: # El intento actual + 2 reintentos
                print(f"--- [VERIFIER] RESULTADO: FALLIDO. Reintentando (Intento {attempts})... ---")
                return "REINTENTAR"
            else:
                print("--- [VERIFIER] RESULTADO: FALLIDO (Máximos intentos alcanzados) ---")
                return "FALLIDO"

    except Exception as e:
        print(f"Error en el Verifier: {e}")
        return "ERROR"

if __name__ == "__main__":
    status = verify_task()
    # Aquí es donde tu orquestador principal (el que llama a todos los .py) 
    # decidiría si vuelve a ejecutar el Executor.py
    with open(r'C:\Users\elmik\Downloads\DAI\Verifier\verification_result.json', 'w') as f:
        json.dump({"status": status}, f)
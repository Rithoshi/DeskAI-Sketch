import json
import subprocess
import os
import sys
import datetime

def save_execution_log(plan, success, stdout='', stderr='', returncode=None):
    log_file = os.path.join(os.path.dirname(__file__), 'execution_log.json')
    timestamp = datetime.datetime.now().isoformat()
    
    entry = {
        "timestamp": timestamp,
        "plan": plan,
        "success": success,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode
    }
    
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            logs = []
    else:
        logs = []
    
    logs.append(entry)
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)

def execute_task(plan_path):
    plan_path = os.path.abspath(plan_path)
    print(f"--- [EXECUTOR] Leyendo plan de: {plan_path} ---")

    try:
        with open(plan_path, 'r', encoding='utf-8') as f:
            plan = json.load(f)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo del plan en {plan_path}")
        return

    plan_dir = os.path.dirname(plan_path)
    critic_status = plan.get('critic', {}).get('status', 'FAILED')

    if critic_status == 'PASSED':
        script_to_run = plan.get('script')
        if not script_to_run:
            print("Error: El plan no contiene el nombre del script a ejecutar.")
            return

        if not os.path.isabs(script_to_run):
            script_path = os.path.normpath(os.path.join(plan_dir, script_to_run))
        else:
            script_path = os.path.normpath(script_to_run)

        language = plan.get('language', '').lower()
        if not language:
            ext = os.path.splitext(script_path)[1].lower()
            if ext == '.bat':
                language = 'bat'
            elif ext == '.py':
                language = 'python'

        if not os.path.exists(script_path):
            print(f"Error: No se encontró el script en {script_path}")
            return

        print(f"Critic aprobó la tarea. Ejecutando: {script_path} ({language})")

        try:
            if language == 'bat':
                result = subprocess.run(script_path, capture_output=True, text=True, shell=True)
            elif language == 'python':
                result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
            else:
                print(f"Lenguaje '{language}' no soportado por el Executor actualmente.")
                return

            if result.returncode == 0:
                print("--- [EXECUTOR] Tarea ejecutada con éxito ---")
                print("Salida:", result.stdout)
                save_execution_log(plan, True, result.stdout, result.stderr, result.returncode)
            else:
                print("--- [EXECUTOR] La tarea falló durante la ejecución ---")
                print("Error:", result.stderr)
                save_execution_log(plan, False, result.stdout, result.stderr, result.returncode)

        except Exception as e:
            print(f"Error crítico durante la ejecución: {e}")
            save_execution_log(plan, False, stderr=str(e))

    else:
        reason = plan.get('critic', {}).get('reason', 'Sin razón especificada')
        print("--- [EXECUTOR] Tarea RECHAZADA por el Critic ---")
        print(f"Razón: {reason}")
        save_execution_log(plan, False, stderr=reason)

if __name__ == "__main__":
    PATH_AL_PLAN = r'c:\Users\elmik\Downloads\DAI\Planner\task_plan.json'
    execute_task(PATH_AL_PLAN)
import ollama
import json
import os
import subprocess
import sys

MODEL_NAME = "qwen2.5-coder:latest"
MAX_CORRECTION_ATTEMPTS = 2


def get_base_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        'router': os.path.join(base_dir, 'Router', 'pipeline_entry.json'),
        'planner_dir': os.path.join(base_dir, 'Planner'),
        'critic_dir': os.path.join(base_dir, 'Critic'),
        'critic_result': os.path.join(base_dir, 'Critic', 'critic_result.json')
    }


def infer_preferred_language(task_description):
    desc = task_description.lower()
    if '.py' in desc or 'python' in desc:
        return 'py'
    if '.bat' in desc or 'batch' in desc:
        return 'bat'
    return None


def build_prompt(task_description, correction_feedback=None, preferred_language=None):
    language_block = ''
    if preferred_language == 'py':
        language_block = (
            "This task explicitly requires a Python script file (\".py\"). "
            "Generate code in Python only, and do not return batch commands. "
            "If the task requires creating another file, write it inside the same folder as the generated Python script using Python file I/O and a relative path. "
            "Use os.path.join(os.path.dirname(__file__), 'filename.py') so the file stays in the Planner directory. "
            "Do not use absolute paths, Desktop paths, or user folders. "
            "If the natural language asks for saving to Desktop, override that and keep all created files inside the Planner folder. "
            "The JSON response must set \"language\": \"py\"."
        )
    elif preferred_language == 'bat':
        language_block = (
            "This task explicitly requires a Windows batch script file (\".bat\"). "
            "Generate code in Batch only. The JSON response must set \"language\": \"bat\"."
        )
    else:
        language_block = (
            "Choose .bat for simple Windows commands or .py for more complex tasks requiring Python."
        )

    if correction_feedback:
        return f"""
        Refina esta tarea usando el feedback del Critic.
        Tarea original: "{task_description}"
        Feedback del Critic: "{correction_feedback}"

        {language_block}

        Responde solo JSON: {{"code": "the executable code", "language": "bat" or "py"}}
        """

    return f"""
    Translate this task into executable code.
    Task: "{task_description}"

    {language_block}

    Responde solo JSON: {{"code": "the executable code", "language": "bat" or "py"}}
    """


def save_plan_and_script(plan, planner_dir):
    code = plan['code']
    language = plan['language']
    filename = os.path.join(planner_dir, f"task_script.{language}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(code)

    plan_filename = os.path.join(planner_dir, 'task_plan.json')
    with open(plan_filename, 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=4, ensure_ascii=False)

    return filename, language


def run_critic(critic_dir):
    command = [sys.executable, os.path.join(critic_dir, 'Critic.py')]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=critic_dir,
        timeout=30
    )
    return result


def load_critic_result(critic_result_path):
    try:
        if os.path.getsize(critic_result_path) == 0:
            return None
        with open(critic_result_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def planner_node():
    paths = get_base_paths()

    # 1. Leer el último estado del router
    try:
        with open(paths['router'], 'r', encoding='utf-8') as f:
            history = json.load(f)

        last_entry = history[-1]
        if last_entry['classification'] != 'Tarea':
            return None

        task_description = last_entry['input']
    except (FileNotFoundError, IndexError):
        return {"error": "No hay tareas pendientes en el JSON."}

    correction_feedback = None
    attempt = 0
    critic_result = None
    preferred_language = infer_preferred_language(task_description)

    while attempt <= MAX_CORRECTION_ATTEMPTS:
        prompt = build_prompt(task_description, correction_feedback, preferred_language)
        response = ollama.generate(
            model=MODEL_NAME,
            prompt=prompt,
            format="json",
            options={"temperature": 0.2}
        )

        try:
            plan = json.loads(response['response'])
        except Exception as e:
            return {"error": f"Error en el Planner al parsear JSON: {e}", "raw": response['response']}

        try:
            script_file, language = save_plan_and_script(plan, paths['planner_dir'])
        except Exception as e:
            return {"error": f"Error al guardar el plan o script: {e}"}

        critic_process = run_critic(paths['critic_dir'])
        critic_result = load_critic_result(paths['critic_result'])

        if critic_result is None:
            return {
                "error": "El Critic no generó critic_result.json",
                "critic_stdout": critic_process.stdout,
                "critic_stderr": critic_process.stderr
            }

        if critic_result.get('status') == 'PASSED':
            full_plan = {
                "script": script_file,
                "language": language,
                "critic": critic_result,
                "attempts": attempt + 1
            }
            plan_filename = os.path.join(paths['planner_dir'], 'task_plan.json')
            with open(plan_filename, 'w', encoding='utf-8') as f:
                json.dump(full_plan, f, indent=4, ensure_ascii=False)
            return full_plan

        correction_feedback = critic_result.get('feedback', '')
        attempt += 1

    return {
        "error": "El Planner no pudo corregir el plan tras recibir feedback del Critic.",
        "critic": critic_result,
        "attempts": attempt
    }


# Ejemplo de ejecución manual del nodo
if __name__ == "__main__":
    plan_generado = planner_node()
    print("Plan de ejecución:", plan_generado)

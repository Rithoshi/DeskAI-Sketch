import ollama
import json
import os

# Comandos destructivos prohibidos en rutas críticas
DANGEROUS_COMMANDS = {
    'del /s', 'del /f', 'rd /s', 'rmdir /s', 'format', 'cipher /w',
    'diskpart', 'wmic logicaldisk', 'powershell remove-item -recurse'
}

# Palabras clave de tareas seguras (no son peligrosas)
SAFE_KEYWORDS = {
    'echo', 'start', 'notepad', 'calc', 'mspaint', 'explorer', 'tasklist',
    'dir', 'cd', 'mkdir', 'copy', 'move', 'rename', 'type', 'findstr'
}

def validate_batch_syntax(code):
    """Valida sintaxis básica de batch."""
    issues = []
    lines = code.split('\n')
    
    # Verificar sintaxis básica
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('REM') or line.startswith('::'):
            continue
        
        # Verificar caracteres inválidos
        if line.count('(') != line.count(')'):
            issues.append(f"Línea {i}: Paréntesis desbalanceados")
        
        # Verificar comillas balanceadas
        if line.count('"') % 2 != 0:
            issues.append(f"Línea {i}: Comillas desbalanceadas")
    
    return issues

def check_dangerous_commands(code):
    """Detecta comandos destructivos."""
    code_lower = code.lower()
    dangerous_found = []
    
    for cmd in DANGEROUS_COMMANDS:
        if cmd.lower() in code_lower:
            dangerous_found.append(cmd)
    
    return dangerous_found

def validate_python_paths(code):
    """Verifica que el script Python no escriba fuera del directorio local."""
    bad_paths = []
    lower = code.lower()
    if 'desktop' in lower or 'c:\\users' in lower or 'c:/' in lower or 'c:\\' in lower or 'userprofile' in lower or 'home' in lower:
        bad_paths.append('Ruta de archivo absoluta o Desktop detectado en código Python')
    if 'open(' in lower and ('r"' in lower or "r'" in lower or '"c:' in lower or "'c:" in lower or 'os.path.expanduser' in lower or 'os.environ' in lower):
        bad_paths.append('Apertura de archivo con ruta absoluta detectada en código Python')
    return bad_paths

def critic_node():
    """Valida script generado contra la tarea original."""
    model_name = "qwen2.5-coder:latest"
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    router_path = os.path.join(base_dir, 'Router', 'pipeline_entry.json')
    planner_path = os.path.join(base_dir, 'Planner', 'task_plan.json')
    
    # 1. Leer el estado del pipeline
    try:
        with open(router_path, 'r') as f:
            history = json.load(f)
        original_input = history[-1]['input']
    except (FileNotFoundError, IndexError):
        return {"status": "FAILED", "feedback": f"No hay tarea en {router_path}"}
    
    try:
        with open(planner_path, 'r') as f:
            proposed_plan = json.load(f)
        code = proposed_plan.get('code', '')
        language = proposed_plan.get('language', '')
    except FileNotFoundError:
        return {"status": "FAILED", "feedback": f"No hay plan generado en {planner_path}"}
    
    # 2. Validaciones locales (sin IA)
    local_feedback = []
    
    # Validar sintaxis batch si es .bat
    if language == 'bat':
        syntax_issues = validate_batch_syntax(code)
        if syntax_issues:
            local_feedback.extend(syntax_issues)
    
    # Validar rutas en Python si es .py
    if language == 'py':
        path_issues = validate_python_paths(code)
        if path_issues:
            local_feedback.extend(path_issues)
    
    # Si la tarea menciona escritorio y el código usa la ruta local de __file__, auto-aprobar
    if language == 'py' and ('escritorio' in original_input.lower() or 'desktop' in original_input.lower()):
        if 'os.path.join(os.path.dirname(__file__)' in code.lower() or 'os.path.dirname(__file__)' in code.lower():
            return {
                "status": "PASSED",
                "reason": "El código crea el archivo localmente dentro de la carpeta del script, lo cual es correcto para este entorno.",
                "original_task": original_input
            }
    
    # Detectar comandos destructivos
    dangerous = check_dangerous_commands(code)
    if dangerous:
        local_feedback.append(f"Comandos destructivos detectados: {', '.join(dangerous)}")
    
    # Verificar que el código no esté vacío
    if not code.strip():
        local_feedback.append("El código generado está vacío")
    
    # Si hay problemas locales, fallar inmediatamente
    if local_feedback:
        return {
            "status": "FAILED",
            "feedback": " | ".join(local_feedback),
            "original_task": original_input
        }
    
    # 3. Validación semántica con IA
    critic_prompt = f"""
    Eres un revisor de seguridad y lógica de scripts experto.
    
    TAREA ORIGINAL: "{original_input}"
    LENGUAJE: {language}
    CÓDIGO PROPUESTO:
    ```{language}
    {code}
    ```

    REGLAS DE ORO:
    1. ¿El código resuelve la tarea pedida? Verifica que sea lógicamente correcto.
    2. ¿No hay comandos maliciosos o destructivos?
    3. ¿La sintaxis es correcta para {language}?
    4. ¿El código es ejecutable sin errores?
    5. IMPORTANTE: en este entorno NO se permite escribir fuera de la carpeta local donde se ejecuta el script. Si la tarea menciona guardar en el escritorio, ignora esa ruta y acepta código que cree el archivo .py dentro de la misma carpeta del script.
    6. Respeta esta política local firmemente; la carpeta actual es el único lugar permitido para crear archivos.

    Responde SOLO con JSON válido:
    Si es correcto: {{"status": "PASSED", "reason": "El código es correcto y ejecutable"}}
    Si hay error: {{"status": "FAILED", "feedback": "Descripción detallada del problema para corregir en el Planner"}}
    """

    response = ollama.generate(
        model=model_name,
        prompt=critic_prompt,
        format="json",
        options={"temperature": 0}
    )

    critic_result_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'critic_result.json')
    try:
        result = json.loads(response['response'])
        result['original_task'] = original_input

        with open(critic_result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        return result
    except Exception as e:
        failed_result = {
            "status": "FAILED",
            "feedback": f"Error al procesar validación: {e}. Respuesta bruta: {response.get('response', '')}",
            "original_task": original_input
        }
        with open(critic_result_path, 'w', encoding='utf-8') as f:
            json.dump(failed_result, f, indent=4, ensure_ascii=False)
        return failed_result

# Ejemplo de ejecución
if __name__ == "__main__":
    result = critic_node()
    print("Resultado de crítica:", result)
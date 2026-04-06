import ollama
import json
import os

def router_node(user_input):
    model_name = "qwen2.5-coder:latest" # O "qwen2.5:0.5b" para máxima velocidad
    
    prompt = f"""
    Clasifica el siguiente mensaje como 'Chat' o 'Tarea'. 
    Responde solo con un objeto JSON en el formato: {{"type": "Chat"}} o {{"type": "Tarea"}}
    Mensaje: "{user_input}"
    """
    
    response = ollama.generate(
        model=model_name,
        prompt=prompt,
        format="json", # Forzamos el modo JSON de Ollama
        options={"temperature": 0} # Temperatura 0 para consistencia técnica
    )
    
    try:
        data = json.loads(response['response'])
        # Guardamos el mensaje original junto a la clasificación
        final_output = {
            "input": user_input,
            "classification": data.get("type", "unknown")
        }
        
        if final_output["classification"] == "Chat":
            chat_prompt = f"Respond to this message as a helpful AI assistant: {user_input}"
            chat_response = ollama.generate(
                model=model_name,
                prompt=chat_prompt,
                options={"temperature": 0.7}
            )
            final_output["response"] = chat_response['response'].strip()
        
        return final_output
    except Exception as e:
        return {"error": f"Error al parsear JSON: {e}"}
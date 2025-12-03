import google.generativeai as genai
from .base_client import BaseLLMClient

class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float,
        reasoning_effort: str = "medium",
        text_verbosity: str = "low"
    ) -> str:
        # Gemini typically combines system instructions or puts them in the first prompt
        # Newer Gemini models support system_instruction in GenerativeModel constructor, 
        # but here we initialize once. We can pass it in generate_content if supported or prepend.
        
        # For simplicity and compatibility, we'll prepend the system prompt.
        # Or we can use the system_instruction argument if we re-instantiate or if the lib supports it per call.
        # Let's try prepending for now as it's robust.
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=30000, # Adjust as needed
        )

        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

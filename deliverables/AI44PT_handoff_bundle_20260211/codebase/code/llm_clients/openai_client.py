from openai import OpenAI
from .base_client import BaseLLMClient

class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float,
        reasoning_effort: str = "medium",
        text_verbosity: str = "low"
    ) -> str:
        full_prompt_for_record = f"{system_prompt}\n\n{user_prompt}"
        
        try:
            # Try using the new responses API if available (as seen in original code)
            # Note: This seems to be a specific custom or preview API usage in the original code
            # If it fails, we fall back to standard chat completions
            response = self.client.responses.create(
                model=self.model,
                input=full_prompt_for_record,
                reasoning={"effort": reasoning_effort},
                text={"verbosity": text_verbosity},
            )
            return response.output_text
        except Exception as primary_error:
            # Fallback to standard Chat Completions API
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=30000,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except Exception as secondary_error:
                raise Exception(f"Primary error: {primary_error}; Fallback error: {secondary_error}")

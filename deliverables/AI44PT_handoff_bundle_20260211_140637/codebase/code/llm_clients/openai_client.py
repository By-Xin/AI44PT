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
        model_name = str(self.model or "").lower()
        is_gpt5_family = model_name.startswith("gpt-5")

        try:
            # Prefer Responses API and keep system/user separation.
            request_kwargs = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "reasoning": {"effort": reasoning_effort},
                "text": {"verbosity": text_verbosity},
            }
            if not is_gpt5_family:
                request_kwargs["temperature"] = temperature

            response = self.client.responses.create(**request_kwargs)

            output_text = getattr(response, "output_text", None)
            if output_text:
                return output_text

            # Best-effort fallback for SDK variants that do not expose output_text.
            output = getattr(response, "output", None) or []
            chunks = []
            for item in output:
                for content in getattr(item, "content", []) or []:
                    text = getattr(content, "text", None)
                    if text:
                        chunks.append(text)
            if chunks:
                return "\n".join(chunks)
            raise RuntimeError("Responses API returned empty output")
        except Exception as primary_error:
            # Fallback to standard Chat Completions API
            try:
                fallback_kwargs = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "max_completion_tokens": 30000,
                }
                if not is_gpt5_family:
                    fallback_kwargs["temperature"] = temperature

                response = self.client.chat.completions.create(**fallback_kwargs)
                return response.choices[0].message.content
            except Exception as secondary_error:
                raise RuntimeError(
                    f"Primary error: {primary_error}; Fallback error: {secondary_error}"
                )

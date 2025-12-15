import os
import logging

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from .base_client import BaseLLMClient


class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        """
        Gemini LLM client with optional dependency and quiet logging.
        Raises ImportError if google-generativeai is missing.
        """
        if genai is None:
            raise ImportError("google-generativeai is not installed. Install it or remove 'gemini' from ENABLED_PROVIDERS.")

        # Reduce noisy gRPC/absl logs (best-effort; safe to ignore failures)
        try:
            os.environ.setdefault("GRPC_PYTHON_FORK_SUPPORT", "0")
            os.environ.setdefault("GRPC_PYTHON_FORK_SUPPORT_ENABLED", "0")
        except Exception:
            pass
        try:
            from absl import logging as absl_logging
            absl_logging.set_verbosity(absl_logging.ERROR)
            absl_logging.use_python_logging()
        except Exception:
            pass
        logging.getLogger("grpc").setLevel(logging.ERROR)

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
        """
        Generate a response using Gemini. System prompt is prepended for compatibility.
        """
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=30000,
        )

        try:
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseLLMClient(ABC):
    @abstractmethod
    def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float,
        reasoning_effort: str = "medium",
        text_verbosity: str = "low"
    ) -> str:
        pass

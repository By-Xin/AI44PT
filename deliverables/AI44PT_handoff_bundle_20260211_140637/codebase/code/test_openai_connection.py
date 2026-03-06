import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

from logging_utils import setup_logging, get_logger

# Add the current directory to sys.path to allow imports
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from config import Config
from llm_clients.openai_client import OpenAIClient


def test_openai():
    # Load environment variables
    load_dotenv()
    setup_logging(logging.INFO)
    logger = get_logger(__name__)

    logger.info("=" * 50)
    logger.info("Testing OpenAI Connection")
    logger.info("=" * 50)

    # Initialize Config
    config = Config()

    # Check API Key
    if not config.OPENAI_API_KEY:
        logger.error("❌ Error: OPENAI_API_KEY not found in environment variables.")
        return

    logger.info("Model: %s", config.CLS_MODEL)
    logger.info("API Key: %s...%s", config.OPENAI_API_KEY[:8], config.OPENAI_API_KEY[-4:])

    # Initialize Client
    try:
        client = OpenAIClient(
            api_key=config.OPENAI_API_KEY,
            model=config.CLS_MODEL
        )
        logger.info("✅ Client initialized successfully.")
    except Exception as e:
        logger.exception("❌ Error initializing client: %s", e)
        return

    # Test Generation
    logger.info("Sending test request...")
    system_prompt = "You are a helpful assistant."
    user_prompt = "Say 'Hello, OpenAI connection is working!' and tell me what model you are."

    try:
        response = client.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            reasoning_effort="low",  # Using low for a quick test
            text_verbosity="low"
        )

        logger.info("✅ Response received:")
        logger.info("-" * 20)
        logger.info("%s", response)
        logger.info("-" * 20)

    except Exception as e:
        logger.exception("❌ Error during generation: %s", e)
        return

if __name__ == "__main__":
    test_openai()

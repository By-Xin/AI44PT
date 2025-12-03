import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the current directory to sys.path to allow imports
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from config import Config
from llm_clients.openai_client import OpenAIClient

def test_openai():
    # Load environment variables
    load_dotenv()
    
    print("="*50)
    print("Testing OpenAI Connection")
    print("="*50)

    # Initialize Config
    config = Config()
    
    # Check API Key
    if not config.OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY not found in environment variables.")
        return

    print(f"Model: {config.CLS_MODEL}")
    print(f"API Key: {config.OPENAI_API_KEY[:8]}...{config.OPENAI_API_KEY[-4:]}")
    
    # Initialize Client
    try:
        client = OpenAIClient(
            api_key=config.OPENAI_API_KEY,
            model=config.CLS_MODEL
        )
        print("✅ Client initialized successfully.")
    except Exception as e:
        print(f"❌ Error initializing client: {e}")
        return

    # Test Generation
    print("\nSending test request...")
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
        
        print("\n✅ Response received:")
        print("-" * 20)
        print(response)
        print("-" * 20)
        
    except Exception as e:
        print(f"\n❌ Error during generation: {e}")

    # response = client.chat.completions.with_raw_response.create(
    #     model=config.CLS_MODEL,
    #     messages=[
    #         {"role": "system", "content": system_prompt},
    #         {"role": "user", "content": user_prompt}
    #     ],
    #     temperature=0.1,
    #     reasoning_effort="low",
    #     text_verbosity="low",
    #     max_tokens=20
    # )

    print("Rate Limit Info:")
    print(f"  Requests limit: {response.headers.get('x-ratelimit-limit-requests')}")
    print(f"  Tokens limit: {response.headers.get('x-ratelimit-limit-tokens')}")
    print(f"  Remaining requests: {response.headers.get('x-ratelimit-remaining-requests')}")

if __name__ == "__main__":
    test_openai()

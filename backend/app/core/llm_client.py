import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def call_llm(system_prompt: str, user_message: str, model: str = None) -> str:
    model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    retries = 3
    wait    = 10  # seconds

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content

        except Exception as e:
            error = str(e)
            if "rate_limit_exceeded" in error and attempt < retries - 1:
                print(f"Rate limit hit. Waiting {wait} seconds before retry...")
                time.sleep(wait)
                wait *= 2  # double wait each retry
            else:
                raise e
            
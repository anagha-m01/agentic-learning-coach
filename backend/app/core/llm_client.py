import time

from groq import Groq

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

client = Groq(api_key=settings.groq_api_key)


def call_llm(system_prompt: str, user_message: str, model: str = None) -> str:
    model = model or settings.groq_model
    retries = 3
    wait = 10  # seconds

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
                logger.warning(f"LLM rate limit hit, retrying in {wait}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
                wait *= 2  # Exponential backoff
            else:
                logger.error(f"LLM call failed: {error}")
                raise
            
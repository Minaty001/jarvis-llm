import os

class Config:

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

    DEFAULT_PROVIDER = os.getenv(
        "DEFAULT_PROVIDER",
        "groq"
    )

    DEFAULT_MODEL = os.getenv(
        "DEFAULT_MODEL",
        "llama-3.3-70b-versatile"
    )

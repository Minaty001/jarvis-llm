from providers.groq_provider import GroqProvider

class ModelRouter:

    def __init__(self):

        self.groq = GroqProvider()

    def generate(
        self,
        messages,
        provider,
        model
    ):

        if provider == "groq":
            return self.groq.generate(
                messages,
                model
            )

        raise Exception(
            f"Unknown provider: {provider}"
        )

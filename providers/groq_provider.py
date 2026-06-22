from openai import OpenAI
from config import Config

class GroqProvider:

    def __init__(self):

        self.client = OpenAI(
            api_key=Config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )

    def generate(
        self,
        messages,
        model
    ):

        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )

        return (
            response
            .choices[0]
            .message
            .content
        )

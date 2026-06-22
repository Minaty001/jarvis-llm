from fastapi import FastAPI

from pydantic import BaseModel

from router.model_router import ModelRouter

app = FastAPI()

router = ModelRouter()

class ChatRequest(BaseModel):

    message: str

    system_prompt: str = ""

    provider: str = "groq"

    model: str = "llama-3.3-70b-versatile"


@app.post("/chat")
async def chat(req: ChatRequest):

    messages = []

    if req.system_prompt:

        messages.append(
            {
                "role": "system",
                "content": req.system_prompt
            }
        )

    messages.append(
        {
            "role": "user",
            "content": req.message
        }
    )

    reply = router.generate(
        messages,
        req.provider,
        req.model
    )

    return {
        "reply": reply
    }

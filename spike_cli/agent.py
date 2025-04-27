import os
from openai import OpenAI

class OpenAIAgent:
    """A simple chat agent that keeps history and talks to OpenAI v1."""
    def __init__(self, system_prompt: str, model: str = "gpt-4"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in environment")

        self.client = OpenAI(api_key=api_key)  
        self.model = model
        self.history = [
            {"role": "system", "content": system_prompt}
        ]

    def process(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=self.history
        )
        assistant_msg = resp.choices[0].message.content

        self.history.append({"role": "assistant", "content": assistant_msg})
        return assistant_msg
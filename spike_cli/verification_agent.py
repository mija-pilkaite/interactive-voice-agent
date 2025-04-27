import os
import re
import json
import asyncio
from typing import Callable, Dict, Tuple
from openai import OpenAI

class VerificationAgent:
    """
    A verification agent that drives the insurance flow using GPT-4,
    supporting both synchronous and streaming interactions.

    Methods:
    - process(user_input) -> (full_reply: str, new_state: dict)
    - stream(user_input, nl_callback, state_callback) -> async
    """
    def __init__(self, config: dict):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        tpl     = config["agent"]["system_prompt_template"]
        patient = config["patient"]
        system_prompt = tpl.format(**patient)

        # Seed initial JSON state
        self.initial_state = {
            "member_id":             patient["member_id"],
            "patient_name":          patient["patient_name"],
            "date_of_birth":         patient["date_of_birth"],
            "insurance_active_to":   None,
            "date_of_treatment":     None,
            "visit_limit":           None,
            "visit_limit_structure": None,
            "visits_used":           None,
            "copay":                 None,
            "deductible":            None,
            "deductible_met":        None,
            "out_of_pocket_maximum": None,
            "out_of_pocket_met":     None,
            "initial_authorization": None,
            "reference_number":      None
        }
        # Build conversation history with a pseudo-turn to prompt first question
        self.history = [
            {"role": "system",    "content": system_prompt},
            {"role": "assistant", "content": f"```json\n{json.dumps(self.initial_state)}\n```"}
        ]
        self.model = config["agent"]["model"]

    def process(self, rep_utterance: str) -> Tuple[str, Dict[str, str]]:
        """
        Synchronous call: send user input and return the full assistant message plus any updated JSON state.
        """
        self.history.append({"role": "user", "content": rep_utterance})
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=self.history
        )
        assistant_msg = resp.choices[0].message.content
        self.history.append({"role": "assistant", "content": assistant_msg})
        new_state = {}
        match = re.search(r"```json\s*(\{.*?\})\s*```", assistant_msg, flags=re.S)
        if match:
            try:
                new_state = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return assistant_msg, new_state

    async def stream(
        self,
        rep_utterance: str,
        nl_callback: Callable[[str], None],
        state_callback: Callable[[Dict[str, str]], None]
    ) -> None:
        """
        Streaming call: streams assistant tokens to `nl_callback`, then extracts JSON and calls `state_callback`.
        """
        # Append user turn
        self.history.append({"role": "user", "content": rep_utterance})
        # Start streaming completion
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            stream=True
        )
        # Buffer to accumulate full assistant text
        buffer = ""
        # Iterate over streamed chunks
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                nl_callback(delta)
                buffer += delta
        # Append full reply to history
        self.history.append({"role": "assistant", "content": buffer})
        # Extract and report new JSON state
        match = re.search(r"```json\s*(\{.*?\})\s*```", buffer, flags=re.S)
        if match:
            try:
                state_callback(json.loads(match.group(1)))
            except json.JSONDecodeError:
                pass

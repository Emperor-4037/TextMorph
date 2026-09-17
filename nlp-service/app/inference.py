import logging
from typing import Optional
from .prompts import TASK_PROMPTS

logger = logging.getLogger("nlp-service")

def build_messages(task: str, text: str, tone_target: Optional[str] = None) -> list:
    system_prompt = TASK_PROMPTS.get(task)
    if system_prompt is None:
        raise ValueError(f"Unknown task: {task}")

    user_content = text
    if task == "tone" and tone_target:
        user_content = f"Target tone: {tone_target}\n\n{text}"
    elif task == "paraphrase" and tone_target:
        user_content = f"Paraphrase in a {tone_target} tone:\n\n{text}"
    elif task == "simplify" and tone_target:
        # tone_target here is actually reading_level
        user_content = f"Simplify to {tone_target} reading level:\n\n{text}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

def run_inference(
    model,
    task: str,
    text: str,
    tone_target: Optional[str] = None,
    max_tokens: int = 1024,
) -> str:
    messages = build_messages(task, text, tone_target)
    response = model.create_chat_completion(
        messages=messages,
        max_tokens=min(max_tokens, 1024),
        temperature=0.3,
        top_p=0.9,
        repeat_penalty=1.1,
    )
    result = response["choices"][0]["message"]["content"]
    return result.strip()

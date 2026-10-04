MODEL_NAME = "qwen2.5:0.5b"


def request_payload(question: str) -> dict[str, object]:
    return {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": question}],
    }

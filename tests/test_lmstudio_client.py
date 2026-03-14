import responses

from models.lmstudio_client import LMStudioClient


@responses.activate
def test_lmstudio_client_chat() -> None:
    client = LMStudioClient(
        base_url="http://localhost:1234/v1",
        model="test-model",
        temperature=0.1,
        max_tokens=10,
        timeout=5,
    )
    responses.add(
        responses.POST,
        "http://localhost:1234/v1/chat/completions",
        json={"choices": [{"message": {"content": "hello"}}]},
        status=200,
    )
    output = client.chat([{"role": "user", "content": "hi"}])
    assert output == "hello"

from hub.api.routes_openai_compat import ChatMessage, _select_persona


def test_explicit_gpt_metadata_is_not_stolen_by_gemini_short_alias() -> None:
    persona, _, reason = _select_persona(
        [ChatMessage(role="user", content="connection test")],
        {"persona": "gpt"},
    )
    assert persona.id == "gpt"
    assert reason == "metadata:gpt"


def test_exact_short_alias_still_routes() -> None:
    persona, _, _ = _select_persona(
        [ChatMessage(role="user", content="connection test")],
        {"persona": "g"},
    )
    assert persona.id == "gemini"

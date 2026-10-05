"""Run from the project root:   python check_setup.py

Tests your Tavily key and EACH OpenRouter model separately, using a realistic
mini itinerary request, and prints the time each model needs.
Keys are never printed.
"""
import time

from tools.config import get_secret

TEST_PROMPT = (
    "Return ONLY valid JSON, no explanation, for a 2-day Paris trip with exactly this shape: "
    '{"days":[{"day":1,"activities":[{"name":"REAL place","description":"short"}]},'
    '{"day":2,"activities":[{"name":"REAL place","description":"short"}]}]}'
)


def main() -> None:
    print("=== TravelMind setup check ===")

    for name in ("OPENROUTER_API_KEY", "TAVILY_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_FALLBACK_MODELS"):
        print(f"{name}: {'FOUND' if get_secret(name) else 'MISSING'}")

    print("\n--- Tavily ---")
    try:
        from tools.web_search import search_web

        results = search_web("Paris top attractions", max_results=3)
        print(f"OK - {len(results)} results. First: {results[0]['title'] if results else 'none'}")
    except Exception as error:
        print(f"FAILED - {type(error).__name__}: {error}")

    print("\n--- OpenRouter (each model tested on its own, realistic mini plan) ---")
    try:
        from agent.agent import _client, _models, _parse_json

        for model in _models():
            started = time.monotonic()
            try:
                response = _client().chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You return only JSON."},
                        {"role": "user", "content": TEST_PROMPT},
                    ],
                    temperature=0,
                    max_tokens=2500,
                )
                seconds = time.monotonic() - started
                text = (response.choices[0].message.content or "").strip() if response.choices else ""
                data = _parse_json(text)

                if data and isinstance(data.get("days"), list) and len(data["days"]) >= 2:
                    print(f"OK      {model}  (valid plan JSON, {seconds:.1f}s)")
                else:
                    print(f"WEAK    {model}  ({seconds:.1f}s, no usable JSON): {text[:100]!r}")
            except Exception as error:
                print(f"FAILED  {model}  -> {type(error).__name__}: {str(error)[:150]}")
    except Exception as error:
        print(f"FAILED - {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
    

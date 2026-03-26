import json
import os
import sys

from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app.main import app


PROMPTS = {
    "emergency": "Right now there is a strong gas smell from a manhole in Queens and two people feel dizzy.",
    "noise": "There is a loud party with music every weekend at 2am in Brooklyn.",
    "trash_rats": "Overflowing garbage bags have been left on the sidewalk outside 200 Atlantic Ave in Brooklyn for three days. Rats were seen near the trash.",
    "irrelevant": "Can you recommend a restaurant nearby?",
}


def main() -> None:
    client = TestClient(app)
    for name, prompt in PROMPTS.items():
        response = client.post("/api/execute", json={"prompt": prompt}, timeout=30)
        response.raise_for_status()
        data = response.json()
        thoughts = [step["response"] for step in data["steps"] if step["module"] == "Agent_Thought"]
        actions = [item.get("action") for item in thoughts]
        modes = [item.get("reasoning_mode") for item in thoughts]
        planner_used = any(item.get("planner_used") for item in thoughts)

        print(f"CASE={name}")
        print("  ACTIONS=", actions)
        print("  MODES=", modes)
        print("  PLANNER_USED=", planner_used)
        print("  RESPONSE=", data["response"].splitlines()[1] if data.get("response") else "")
        print("  TRACE_HEAD=", json.dumps(data["steps"][:3], ensure_ascii=True)[:400])
        print()


if __name__ == "__main__":
    main()

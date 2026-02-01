import json
import os

import requests


API_URL = os.getenv("DISPATCH_API_URL", "http://127.0.0.1:8000/api/execute")


def main() -> None:
    payload = {"prompt": "Loud party at 2am in Brooklyn, every weekend."}
    resp = requests.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    required_keys = {"status", "error", "response", "steps"}
    missing = required_keys - set(data.keys())
    assert not missing, f"Missing top-level keys: {missing}"
    assert isinstance(data["steps"], list), "steps must be a list"
    for step in data["steps"]:
        for key in ("module", "prompt", "response"):
            assert key in step, f"Step missing {key}"

    print("Sanity check passed")
    print(json.dumps(data, indent=2)[:1000])


if __name__ == "__main__":
    main()

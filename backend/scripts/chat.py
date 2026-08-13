"""Dev script for testing the chat endpoint locally.

Previously used tu.get_subway() (TuneAPI REST client); now uses httpx directly.
"""
import httpx
from fire import Fire

ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmZhNTBiOWEtYjg4ZC00ZjY4LWI3MTEtOTRlZDcxMzFjODg2IiwiZXhwIjoxNzUxNzIwMjM4LCJpYXQiOjE3NTE3MTY2MzgsInR5cGUiOiJhY2Nlc3MifQ.-FgsUc0DeZZ5LOrWy911iO0NWChqEm5E2jEvpDmJx2s"

BASE = "http://localhost:8000/api"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


def main():
    with httpx.Client(headers=HEADERS) as client:
        c = client.post(f"{BASE}/chat").json()
        cid = c["id"]
        print(">>> New conversation created: ", cid)

        m = client.post(
            f"{BASE}/chat/{cid}",
            json={"message": "Hello, how are you?", "stream": False},
        ).json()
        print(">>> New message sent: ", m)


if __name__ == "__main__":
    Fire(main)

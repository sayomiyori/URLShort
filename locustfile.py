"""
Load scenarios for URLShort.

Example:
  locust -f locustfile.py --host=http://localhost:8000 --users=500 --spawn-rate=50

Use the same port as your app (8000 direct, or 8080 behind Nginx).
"""

from __future__ import annotations

import random
import string

from locust import HttpUser, between, task


class URLShortUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hot_codes: list[str] = []
        self.all_codes: list[str] = []

    @task(1)
    def create_url(self) -> None:
        body = {"url": f"https://load.example/{random.random()}"}
        with self.client.post(
            "/api/v1/shorten",
            json=body,
            catch_response=True,
            name="/api/v1/shorten",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                code = data["code"]
                self.all_codes.append(code)
                if len(self.hot_codes) < 10:
                    self.hot_codes.append(code)
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(8)
    def redirect_hot(self) -> None:
        if not self.hot_codes:
            return
        code = random.choice(self.hot_codes)
        self.client.get(f"/{code}", name="GET /[code] hot", allow_redirects=False)

    @task(2)
    def redirect_cold(self) -> None:
        if self.all_codes and random.random() < 0.7:
            code = random.choice(self.all_codes)
        else:
            code = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.client.get(f"/{code}", name="GET /[code] cold", allow_redirects=False)

    @task(1)
    def get_stats(self) -> None:
        if not self.all_codes:
            return
        code = random.choice(self.all_codes)
        self.client.get(f"/api/v1/stats/{code}", name="/api/v1/stats/[code]")

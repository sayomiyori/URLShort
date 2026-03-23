"""
Load scenarios for URLShort.

Example:
  locust -f locustfile.py --host=http://localhost:8012 --users=500 --spawn-rate=50

Use the same port as your app (8012 direct, or 8080 behind Nginx).
"""

from __future__ import annotations

import random
import string

from locust import HttpUser, between, task

# Status codes that are intentional / non-error outcomes.
_REDIRECT_OK = {301, 302, 404, 429}   # 404 = expired/missing, 429 = rate-limited
_SHORTEN_OK   = {200, 409, 422, 429}
_STATS_OK     = {200, 404, 429}


class URLShortUser(HttpUser):
    wait_time = between(0.5, 2.0)

    # Per-user pools populated in on_start and during the run.
    hot_codes: list[str]
    all_codes: list[str]

    def on_start(self) -> None:
        """Pre-create a few URLs so redirect tasks have valid codes from the first task.
        Uses catch_response so rate-limited (429) warm-up requests are not counted
        as failures — they are expected when 500 users spawn simultaneously."""
        self.hot_codes = []
        self.all_codes = []
        for _ in range(3):
            with self.client.post(
                "/api/v1/shorten",
                json={"url": f"https://warmup.example/{random.random()}"},
                name="/api/v1/shorten",
                catch_response=True,
            ) as resp:
                if resp.status_code == 200:
                    code = resp.json()["code"]
                    self.hot_codes.append(code)
                    self.all_codes.append(code)
                    resp.success()
                else:
                    resp.success()  # 429 during warm-up is expected, not a failure

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task(1)
    def create_url(self) -> None:
        body = {"url": f"https://load.example/{random.random()}"}
        with self.client.post(
            "/api/v1/shorten",
            json=body,
            catch_response=True,
            name="/api/v1/shorten",
        ) as resp:
            if resp.status_code in _SHORTEN_OK:
                if resp.status_code == 200:
                    code = resp.json()["code"]
                    self.all_codes.append(code)
                    if len(self.hot_codes) < 10:
                        self.hot_codes.append(code)
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(8)
    def redirect_hot(self) -> None:
        """Redirect to a code this user created — should always be 301 or 429."""
        if not self.hot_codes:
            return
        code = random.choice(self.hot_codes)
        with self.client.get(
            f"/{code}",
            name="GET /[code] hot",
            allow_redirects=False,
            catch_response=True,
        ) as resp:
            if resp.status_code in _REDIRECT_OK:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(2)
    def redirect_cold(self) -> None:
        """30% chance of a known code, 70% random — 404 is expected."""
        if self.all_codes and random.random() < 0.3:
            code = random.choice(self.all_codes)
        else:
            code = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        with self.client.get(
            f"/{code}",
            name="GET /[code] cold",
            allow_redirects=False,
            catch_response=True,
        ) as resp:
            if resp.status_code in _REDIRECT_OK:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(1)
    def get_stats(self) -> None:
        if not self.all_codes:
            return
        code = random.choice(self.all_codes)
        with self.client.get(
            f"/api/v1/stats/{code}",
            name="/api/v1/stats/[code]",
            catch_response=True,
        ) as resp:
            if resp.status_code in _STATS_OK:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

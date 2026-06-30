"""GitHub adapter — public profile enrichment.

Live GitHub responses are non-deterministic (stars change, rate limits apply),
which conflicts with the "same inputs -> same output" constraint. So the default
path reads a *cached fixture* (``github*.json`` in the inputs dir) that mirrors
the shape of the GitHub REST API: a ``user`` object plus a ``repos`` list. The
``fetch_and_cache`` helper shows how that fixture is produced from the live API,
but it is never called during a normal run.

From the profile we take name, bio (-> headline), blog (-> portfolio link), and
the set of repo languages as skills.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import RawField, SourceRecord

log = logging.getLogger("candidate_transformer.sources.github")

_GITHUB_MARKERS = {"login", "public_repos"}  # identifies a github user blob


class GithubAdapter:
    name = "github"

    def extract(self, inputs_dir: Path) -> list[SourceRecord]:
        out: list[SourceRecord] = []
        for path in sorted(inputs_dir.glob("github*.json")):
            rec = self._extract_file(path)
            if rec and rec.fields:
                out.append(rec)
        return out

    def _extract_file(self, path: Path) -> SourceRecord | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("skipping malformed github fixture %s: %s", path, exc)
            return None

        user = data.get("user", data) if isinstance(data, dict) else None
        if not isinstance(user, dict) or not (_GITHUB_MARKERS & user.keys()):
            return None
        repos = data.get("repos", []) if isinstance(data, dict) else []

        fields: list[RawField] = []

        def add(canonical: str, value: Any, key: str) -> None:
            if value in (None, "", []):
                return
            fields.append(RawField(canonical, value, method=f"github_api:{key}"))

        add("full_name", user.get("name"), "user.name")
        add("headline", user.get("bio"), "user.bio")
        add("location.city", user.get("location"), "user.location")
        add("links.github", user.get("html_url"), "user.html_url")
        add("links.portfolio", user.get("blog"), "user.blog")
        if user.get("email"):
            add("emails", user.get("email"), "user.email")

        # Languages across repos -> skills (deduped, deterministic order).
        languages: list[str] = []
        for repo in repos if isinstance(repos, list) else []:
            lang = repo.get("language") if isinstance(repo, dict) else None
            if lang and lang not in languages:
                languages.append(lang)
        for lang in languages:
            add("skills", lang, "repo.language")

        return SourceRecord(self.name, fields)


def fetch_and_cache(username: str, out_path: Path, token: str | None = None) -> None:
    """Fetch a public GitHub profile + repos and write a fixture file.

    Not used during normal runs — provided so the committed fixture is
    reproducible. Requires ``requests``.
    """
    import requests  # local import: only needed for the live path

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    user = requests.get(
        f"https://api.github.com/users/{username}", headers=headers, timeout=10
    ).json()
    repos = requests.get(
        f"https://api.github.com/users/{username}/repos?per_page=100&sort=pushed",
        headers=headers, timeout=10,
    ).json()
    out_path.write_text(
        json.dumps({"user": user, "repos": repos}, indent=2), encoding="utf-8"
    )

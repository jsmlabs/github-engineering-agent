"""Minimal bounded HTTPS clients. No automatic retries or arbitrary endpoints."""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .core import AgentError, MAX_ISSUE_CHARS, require_repo


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AgentError("Unexpected HTTP redirect; request not followed")


def json_request(url: str, *, token: str, payload: dict | None = None, github: bool = False, max_bytes: int = 1_200_000) -> Any:
    if not token:
        raise AgentError("Missing API credential")
    prefix = "https://api.github.com/" if github else "https://api.openai.com/v1/"
    if not url.startswith(prefix):
        raise AgentError("API endpoint is not allowlisted")
    headers = {"Accept": "application/vnd.github+json" if github else "application/json", "Authorization": "Bearer " + token}
    if github:
        headers["X-GitHub-Api-Version"] = "2026-03-10"
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(data) > 180_000:
            raise AgentError("Request exceeds size budget")
        headers["Content-Type"] = "application/json"
    req = Request(url, headers=headers, data=data, method="POST" if payload is not None else "GET")
    try:
        with build_opener(RejectRedirect()).open(req, timeout=60) as response:
            blob = response.read(max_bytes + 1)
            if len(blob) > max_bytes:
                raise AgentError("API response size exceeded")
            return json.loads(blob)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        # Response body may contain private issue content: never print it.
        if isinstance(exc, HTTPError):
            raise AgentError(f"API request failed: HTTP {exc.code}") from exc
        raise AgentError("API request failed or returned invalid JSON") from exc


class GitHub:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = require_repo(repo)
        self.prefix = f"https://api.github.com/repos/{self.repo}/"

    def get(self, route: str) -> Any:
        return json_request(self.prefix + route, token=self.token, github=True)

    def post(self, route: str, data: dict) -> Any:
        return json_request(self.prefix + route, token=self.token, github=True, payload=data)

    def metadata(self) -> dict:
        x = json_request(f"https://api.github.com/repos/{self.repo}", token=self.token, github=True)
        if not isinstance(x, dict) or x.get("full_name", "").lower() != self.repo.lower() or x.get("archived"):
            raise AgentError("Repository identity mismatch or archived repository")
        branch = x.get("default_branch")
        if not isinstance(branch, str) or not branch or branch.startswith("-"):
            raise AgentError("Missing default branch")
        return x

    def issue(self, number: int) -> dict:
        if type(number) is not int or number < 1:
            raise AgentError("Issue number must be positive")
        x = self.get(f"issues/{number}")
        if not isinstance(x, dict) or "pull_request" in x or x.get("state") != "open" or x.get("number") != number:
            raise AgentError("Expected open issue (not a pull request)")
        if not isinstance(x.get("title"), str) or len(x["title"]) > 250 or not isinstance(x.get("body") or "", str):
            raise AgentError("Invalid issue fields")
        if not isinstance(x.get("updated_at"), str) or not x["updated_at"]:
            raise AgentError("Issue update timestamp is required to detect stale plans")
        if len(x.get("body") or "") > MAX_ISSUE_CHARS:
            raise AgentError("Issue is too long for the bounded context window")
        return x

    def existing_pr(self, branch: str, base: str) -> dict | None:
        owner = self.repo.split("/")[0]
        query = urlencode({"head": f"{owner}:{branch}", "base": base, "state": "all", "per_page": 100})
        prs = self.get(f"pulls?{query}")
        if not isinstance(prs, list):
            raise AgentError("Unexpected PR search result")
        # The API is paginated. A full page cannot prove that no older PR
        # occupies this head branch; fail closed rather than guessing.
        if len(prs) >= 100:
            raise AgentError("PR search results may be incomplete; reconcile manually")
        for pr in prs:
            if pr.get("head", {}).get("ref") == branch and pr.get("base", {}).get("ref") == base:
                if pr.get("state") != "open":
                    raise AgentError("Existing PR is closed; refusing to reuse its branch")
                return pr
        return None


SELECT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"rationale": {"type": "string"}, "paths": {"type": "array", "items": {"type": "string"}}},
    "required": ["rationale", "paths"],
}
EDIT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "edits": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
            "path": {"type": "string"}, "base_sha256": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "base_sha256", "content"]}},
    },
    "required": ["summary", "edits"],
}


class Model:
    def __init__(self, api_key: str, model: str):
        if not api_key or not model:
            raise AgentError("OPENAI_API_KEY and --model are required")
        self.key, self.model = api_key, model

    def ask(self, instructions: str, context: dict, schema: dict, name: str) -> dict:
        request = {
            "model": self.model,
            "instructions": instructions,
            "input": json.dumps(context, ensure_ascii=False),
            "store": False,
            "max_output_tokens": 12_000,
            "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
        }
        result = json_request("https://api.openai.com/v1/responses", token=self.key, payload=request, max_bytes=250_000)
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise AgentError("Model response incomplete, unavailable, or refused")
        messages = result.get("output")
        if not isinstance(messages, list):
            raise AgentError("Malformed model output")
        content = [c for item in messages if isinstance(item, dict) and item.get("type") == "message"
                   for c in (item.get("content") or []) if isinstance(c, dict) and c.get("type") == "output_text"]
        if len(content) != 1 or not isinstance(content[0].get("text"), str):
            raise AgentError("Missing single structured model output")
        try:
            decoded = json.loads(content[0]["text"])
        except ValueError as exc:
            raise AgentError("Invalid structured model output") from exc
        if not isinstance(decoded, dict):
            raise AgentError("Model output must be JSON object")
        return decoded

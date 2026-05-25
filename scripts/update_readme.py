#!/usr/bin/env python3
"""
Auto-update README.md for awesome-quant.

Usage:
    python scripts/update_readme.py

Optional:
    GITHUB_TOKEN=ghp_xxx python scripts/update_readme.py

The script searches GitHub repositories, filters candidates, groups them
into quant-related categories, and rewrites README.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests

README_PATH = Path("README.md")
DATA_DIR = Path("data")
DATA_PATH = DATA_DIR / "github_repos.json"
SEED_SOURCES_PATH = Path("data/seed_sources.txt")

GITHUB_API = "https://api.github.com"

GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)

CATEGORIES: dict[str, list[str]] = {
    "Research Frameworks": [
        'quant research framework stars:>100 fork:false archived:false',
        'quantitative finance research framework stars:>100 fork:false archived:false',
        'algorithmic trading research framework stars:>100 fork:false archived:false',
    ],
    "Backtesting": [
        'backtesting trading Python stars:>500 fork:false archived:false',
        'backtest quantitative finance stars:>200 fork:false archived:false',
        'event driven backtesting trading stars:>100 fork:false archived:false',
    ],
    "Alpha Research": [
        'alpha research quantitative trading stars:>50 fork:false archived:false',
        'factor investing research Python stars:>50 fork:false archived:false',
        'stock factor model quantitative stars:>50 fork:false archived:false',
    ],
    "Portfolio Optimization": [
        'portfolio optimization quantitative finance stars:>100 fork:false archived:false',
        'mean variance optimization Python stars:>50 fork:false archived:false',
        'risk parity portfolio optimization stars:>50 fork:false archived:false',
    ],
    "Risk Modeling": [
        'financial risk model Python stars:>100 fork:false archived:false',
        'value at risk quantitative finance stars:>50 fork:false archived:false',
        'risk management quantitative finance stars:>50 fork:false archived:false',
    ],
    "Market Microstructure": [
        'market microstructure trading stars:>20 fork:false archived:false',
        'limit order book research stars:>20 fork:false archived:false',
        'order book imbalance trading stars:>20 fork:false archived:false',
    ],
    "Execution and HFT": [
        'high frequency trading research stars:>50 fork:false archived:false',
        'trade execution algorithm stars:>20 fork:false archived:false',
        'market making trading bot research stars:>50 fork:false archived:false',
    ],
    "Machine Learning for Trading": [
        'machine learning trading Python stars:>500 fork:false archived:false',
        'deep learning trading quantitative finance stars:>100 fork:false archived:false',
        'reinforcement learning trading stars:>100 fork:false archived:false',
    ],
    "Crypto Quant": [
        'crypto quantitative trading research stars:>50 fork:false archived:false',
        'cryptocurrency backtesting trading stars:>100 fork:false archived:false',
        'defi quantitative research stars:>20 fork:false archived:false',
    ],
    "Data and Feeds": [
        'market data Python trading stars:>100 fork:false archived:false',
        'financial data API Python stars:>100 fork:false archived:false',
        'limit order book data stars:>20 fork:false archived:false',
    ],
    "Academic Resources": [
        'quantitative finance course stars:>50 fork:false archived:false',
        'financial machine learning book code stars:>50 fork:false archived:false',
        'algorithmic trading course stars:>50 fork:false archived:false',
    ],
    "Interview / Learning": [],
    "LLM / AI Agents for Finance": [],
    "Utilities": [
        'technical indicators Python stars:>500 fork:false archived:false',
        'trading indicators Python stars:>100 fork:false archived:false',
        'finance Python library stars:>500 fork:false archived:false',
    ],
    "Source Lists": [],
    "Candidates to Review": [],
}

NEGATIVE_KEYWORDS = {
    "casino",
    "gambling",
    "forex signal",
    "telegram signal",
    "binary option",
    "martingale",
    "guaranteed profit",
    "get rich",
    "pump",
    "terms of service",
    "terms of use",
}

CATEGORY_LIMIT = 20
QUERY_RESULT_LIMIT = 15
MIN_STARS = 20
MAX_DAYS_SINCE_PUSH = 3650

def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "awesome-quant-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code == 403:
        reset = response.headers.get("X-RateLimit-Reset")
        if reset:
            reset_time = dt.datetime.fromtimestamp(int(reset), tz=dt.UTC)
            wait_seconds = (reset_time - dt.datetime.now(dt.UTC)).total_seconds()
            if wait_seconds > 0:
                print(f"Rate limit hit. Sleeping {wait_seconds:.0f}s until {reset_time.strftime('%H:%M:%S UTC')}...", file=sys.stderr)
                time.sleep(wait_seconds + 1.0)
                return request_json(url, headers)
        raise RuntimeError(f"GitHub API returned 403: {response.text[:300]}")

    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API error {response.status_code}: {response.text[:300]}")

    return response.json()


def search_repositories(query: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    encoded = quote(query)
    url = f"{GITHUB_API}/search/repositories?q={encoded}&sort=stars&order=desc&per_page={QUERY_RESULT_LIMIT}"
    data = request_json(url, headers)
    return data.get("items", [])


def load_seed_sources() -> list[str]:
    if not SEED_SOURCES_PATH.exists():
        return []
    return [
        line.strip()
        for line in SEED_SOURCES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def normalize_github_repo_url(url: str) -> str | None:
    match = GITHUB_REPO_RE.search(url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    repo = repo.removesuffix(".git")
    return f"https://github.com/{owner}/{repo}"


def repo_api_path(repo_url: str) -> tuple[str, str] | None:
    normalized = normalize_github_repo_url(repo_url)
    if not normalized:
        return None
    parsed = urlparse(normalized)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def fetch_repo_metadata(owner: str, repo: str, headers: dict[str, str]) -> dict[str, Any] | None:
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    try:
        return request_json(url, headers)
    except Exception as exc:
        print(f"Failed metadata: {owner}/{repo} — {exc}", file=sys.stderr)
        return None


def fetch_readme_text(owner: str, repo: str, default_branch: str = "main") -> str:
    candidates = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/readme.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
    ]
    for url in candidates:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200 and response.text.strip():
                return response.text
        except requests.RequestException:
            pass
    return ""


def extract_github_links(markdown_text: str) -> set[str]:
    links = set()
    for match in GITHUB_REPO_RE.finditer(markdown_text):
        normalized = normalize_github_repo_url(match.group(0))
        if normalized:
            links.add(normalized)
    return links


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_since(value: str | None) -> int:
    parsed = parse_date(value)
    if parsed is None:
        return 99999
    now = dt.datetime.now(dt.UTC)
    return max(0, (now - parsed).days)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = value.replace("\n", " ").replace("|", "\\|")
    value = " ".join(value.split())
    return value.strip()


def is_bad_repo(repo: dict[str, Any]) -> bool:
    name = clean_text(repo.get("full_name")).lower()
    desc = clean_text(repo.get("description")).lower()
    text = f"{name} {desc}"

    if len(desc) > 1000:
        return True
    if repo.get("archived") or repo.get("fork"):
        return True
    if repo.get("stargazers_count", 0) < MIN_STARS:
        return True
    if days_since(repo.get("pushed_at")) > MAX_DAYS_SINCE_PUSH:
        return True
    if any(keyword in text for keyword in NEGATIVE_KEYWORDS):
        return True
    return False


def classify_repo(repo: dict[str, Any]) -> str:
    name = clean_text(repo.get("full_name")).lower()
    desc = clean_text(repo.get("description")).lower()
    text = f"{name} {desc}"

    if "framework" in text and ("research" in text or "quant" in text):
        return "Research Frameworks"
    if "backtest" in text:
        return "Backtesting"
    if "factor" in text or "alpha" in text:
        return "Alpha Research"
    if "portfolio" in text and ("optimiz" in text or "allocation" in text or "parity" in text):
        return "Portfolio Optimization"
    if "risk" in text and ("model" in text or "manag" in text or "value at" in text):
        return "Risk Modeling"
    if "microstructure" in text or "order book" in text or "imbalance" in text:
        return "Market Microstructure"
    if "hft" in text or "high frequency" in text or "execution" in text or "market making" in text:
        return "Execution and HFT"
    if "llm" in text or "agent" in text or "gpt" in text or "large language" in text:
        return "LLM / AI Agents for Finance"
    if "deep learning" in text or "reinforcement learning" in text or "machine learning" in text:
        return "Machine Learning for Trading"
    if "crypto" in text or "bitcoin" in text or "defi" in text:
        return "Crypto Quant"
    if "data" in text and ("api" in text or "feed" in text or "market" in text):
        return "Data and Feeds"
    if "course" in text or "book" in text or "paper" in text or "academic" in text:
        return "Academic Resources"
    if "interview" in text or "learn" in text or "tutorial" in text:
        return "Interview / Learning"
    if "indicator" in text or "library" in text or "util" in text:
        return "Utilities"
    
    return "Candidates to Review"


def repo_score(repo: dict[str, Any]) -> float:
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    pushed_days = days_since(repo.get("pushed_at"))
    recency_score = max(0.0, 1.0 - pushed_days / MAX_DAYS_SINCE_PUSH)
    
    # Give priority boost for repos coming from seed source extraction
    boost = 0.0
    if repo.get("seed_discovered", False):
        boost = 500.0

    return (
        stars * 1.0
        + forks * 2.0
        + recency_score * 500.0
        + boost
        - open_issues * 0.1
    )


def collect_repositories() -> dict[str, list[dict[str, Any]]]:
    headers = github_headers()
    grouped: dict[str, dict[str, dict[str, Any]]] = {
        category: {} for category in CATEGORIES
    }
    seen: set[str] = set()

    # 1. Search API Discovery
    for category, queries in CATEGORIES.items():
        if not queries:
            continue
        print(f"Collecting: {category}", file=sys.stderr)
        for query in queries:
            try:
                repos = search_repositories(query, headers)
            except Exception as exc:
                print(f"  query failed: {query} — {exc}", file=sys.stderr)
                continue

            for repo in repos:
                full_name = repo.get("full_name")
                if not full_name or is_bad_repo(repo):
                    continue
                if full_name in seen:
                    continue
                seen.add(full_name)
                grouped[category][full_name] = repo
            time.sleep(2.5)

    # 2. Seed Sources Discovery
    if not os.getenv("GITHUB_TOKEN"):
        print("Skipping seed source discovery because GITHUB_TOKEN is not set.", file=sys.stderr)
    else:
        seed_sources = load_seed_sources()
        discovered: dict[str, dict[str, Any]] = {}
        for seed_url in seed_sources:
            parsed = repo_api_path(seed_url)
            if not parsed:
                continue
            owner, repo = parsed
            print(f"Reading seed source: {owner}/{repo}", file=sys.stderr)
            seed_meta = fetch_repo_metadata(owner, repo, headers)
            if not seed_meta:
                continue
            
            # Record the seed source itself
            seed_normalized = f"https://github.com/{owner}/{repo}"
            grouped["Source Lists"][f"{owner}/{repo}"] = seed_meta
            seen.add(f"{owner}/{repo}")

            default_branch = seed_meta.get("default_branch") or "main"
            readme_text = fetch_readme_text(owner, repo, default_branch)
            for linked_url in extract_github_links(readme_text):
                if linked_url == seed_normalized:
                    continue
                if linked_url not in discovered:
                    discovered[linked_url] = {"count": 1}
                else:
                    discovered[linked_url]["count"] += 1
            time.sleep(1.5)

        for repo_url, item in discovered.items():
            parsed = repo_api_path(repo_url)
            if not parsed:
                continue
            owner, repo = parsed
            full_name = f"{owner}/{repo}"
            if full_name in seen:
                continue

            meta = fetch_repo_metadata(owner, repo, headers)
            time.sleep(1.0)
            if not meta or is_bad_repo(meta):
                continue
            
            meta["seed_discovered"] = True
            category = classify_repo(meta)
            grouped[category][full_name] = meta
            seen.add(full_name)

    final: dict[str, list[dict[str, Any]]] = {}
    for category, repos_by_name in grouped.items():
        repos = list(repos_by_name.values())
        repos.sort(key=repo_score, reverse=True)
        final[category] = repos[:CATEGORY_LIMIT]

    return final


def repo_to_markdown(repo: dict[str, Any]) -> str:
    name = clean_text(repo.get("full_name"))
    url = repo.get("html_url", "")
    desc = clean_text(repo.get("description")) or "No description provided."
    language = repo.get("language") or "N/A"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    pushed_at = repo.get("pushed_at")
    pushed_date = pushed_at[:10] if pushed_at else "N/A"
    license_info = repo.get("license") or {}
    license_name = license_info.get("spdx_id") or license_info.get("name") or "N/A"

    return (
        f"- [{name}]({url}) — {desc} "
        f"`{language}` · ⭐ {stars:,} · forks {forks:,} · "
        f"updated {pushed_date} · license {license_name}"
    )


def generate_readme(grouped: dict[str, list[dict[str, Any]]]) -> str:
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    contents = "\n".join(
        f"- [{category}](#{category.lower().replace(' ', '-').replace('&', 'and').replace('/', '')})"
        for category in grouped
    )

    lines: list[str] = [
        "# Awesome Quant",
        "",
        "A curated list of quantitative research, trading research, and market microstructure resources.",
        "",
        "The list is automatically refreshed from GitHub repository metadata.",
        "",
        "## Contents",
        "",
        contents,
        "",
    ]

    for category, repos in grouped.items():
        lines.append(f"## {category}")
        lines.append("")
        if not repos:
            lines.append("_No repositories found in this update._")
        else:
            for repo in repos:
                lines.append(repo_to_markdown(repo))
        lines.append("")

    lines.extend(
        [
            "## Contribution Guidelines",
            "",
            "Pull requests are welcome.",
            "",
            "Good additions should be:",
            "",
            "- relevant to quantitative research, trading research, or market structure",
            "- useful for research, reproducibility, education, or infrastructure",
            "- documented well enough for others to evaluate",
            "- actively maintained or historically important",
            "",
            "Please avoid pure signal-selling projects, generic trading bots, or low-quality forks.",
            "",
            "## Disclaimer",
            "",
            "This repository is for research and education only. Nothing here is financial advice.",
            "",
            "---",
            "",
            f"Last auto-generated: {now}",
            "",
        ]
    )
    return "\n".join(lines)


def save_data(grouped: dict[str, list[dict[str, Any]]]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    compact: dict[str, list[dict[str, Any]]] = {}
    for category, repos in grouped.items():
        compact[category] = [
            {
                "full_name": repo.get("full_name"),
                "html_url": repo.get("html_url"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "pushed_at": repo.get("pushed_at"),
                "license": (repo.get("license") or {}).get("spdx_id"),
            }
            for repo in repos
        ]

    DATA_PATH.write_text(
        json.dumps(compact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Generate README content but do not write files.",
    )
    args = parser.parse_args()

    grouped = collect_repositories()
    readme = generate_readme(grouped)

    if args.check:
        print(readme)
        return

    README_PATH.write_text(readme, encoding="utf-8")
    save_data(grouped)

    print(f"Updated {README_PATH}")
    print(f"Saved metadata to {DATA_PATH}")


if __name__ == "__main__":
    main()

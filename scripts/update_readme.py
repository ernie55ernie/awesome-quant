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
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests

README_PATH = Path("README.md")
DATA_DIR = Path("data")
DATA_PATH = DATA_DIR / "github_repos.json"
SEED_SOURCES_PATH = Path("data/seed_sources.txt")
CONFIG_PATH = Path("api_keys.json")

def load_config() -> dict[str, str]:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Warning: Failed to parse {CONFIG_PATH}: {exc}", file=sys.stderr)
    return {}

CONFIG = load_config()

def get_api_key(service: str) -> str | None:
    token = os.getenv(service)
    if token:
        return token
    return CONFIG.get(service)

GITHUB_API = "https://api.github.com"

GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)
ARXIV_RE = re.compile(
    r"https?://arxiv\.org/abs/(\d+\.\d+)"
)
SSRN_RE = re.compile(
    r"https?://papers\.ssrn\.com/sol3/papers\.cfm\?abstract_id=(\d+)"
)
HUGGINGFACE_RE = re.compile(
    r"https?://huggingface\.co/([^/\s]+/[^/\s]+)"
)
HUGGINGFACE_DATASET_RE = re.compile(
    r"https?://huggingface\.co/datasets/([^/\s]+/[^/\s]+)"
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
    "Research Papers & Articles": [],
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
    token = get_api_key("GITHUB_TOKEN")
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


def fetch_arxiv_metadata(arxiv_id: str) -> dict[str, Any] | None:
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entry = root.find('atom:entry', ns)
            if entry is not None:
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.replace('\n', ' ').strip() if title_elem is not None else "Unknown Title"
                authors = []
                for author in entry.findall('atom:author', ns):
                    name_elem = author.find('atom:name', ns)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text)
                
                pub_elem = entry.find('atom:published', ns)
                published = pub_elem.text[:10] if pub_elem is not None else "N/A"
                
                sum_elem = entry.find('atom:summary', ns)
                desc = sum_elem.text.replace('\n', ' ').strip() if sum_elem is not None else ""
                # Shorten description if too long
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                
                return {
                    "type": "paper",
                    "source": "arxiv",
                    "full_name": title,
                    "html_url": f"https://arxiv.org/abs/{arxiv_id}",
                    "description": f"Authors: {', '.join(authors)}. {desc}",
                    "pushed_at": published + "T00:00:00Z" if published != "N/A" else None,
                    "authors": authors
                }
    except Exception as exc:
        print(f"Failed arxiv: {arxiv_id} — {exc}", file=sys.stderr)
    return None


def fetch_ssrn_metadata(ssrn_id: str) -> dict[str, Any] | None:
    url = f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={ssrn_id}"
    try:
        # SSRN blocks headless requests often, add a common User-Agent
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if response.status_code == 200:
            match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
            title = match.group(1).strip() if match else f"SSRN Paper {ssrn_id}"
            title = title.split(" :: SSRN")[0]
            title = html.unescape(title)
            return {
                "type": "paper",
                "source": "ssrn",
                "full_name": title,
                "html_url": url,
                "description": "SSRN Research Paper",
                "pushed_at": None,
            }
    except Exception as exc:
        print(f"Failed ssrn: {ssrn_id} — {exc}", file=sys.stderr)
    return None


def fetch_serpapi_scholar(query: str, api_key: str) -> list[dict[str, Any]]:
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": api_key,
        "num": 5
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("organic_results", [])
        elif response.status_code == 401:
            print("SerpApi Error: Invalid API key.", file=sys.stderr)
        else:
            print(f"SerpApi Error {response.status_code}: {response.text[:200]}", file=sys.stderr)
    except Exception as exc:
        print(f"Failed SerpApi: {query} — {exc}", file=sys.stderr)
    return []



def fetch_huggingface_metadata(hf_id: str, is_dataset: bool = False) -> dict[str, Any] | None:
    api_url = f"https://huggingface.co/api/datasets/{hf_id}" if is_dataset else f"https://huggingface.co/api/models/{hf_id}"
    try:
        response = requests.get(api_url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return {
                "type": "huggingface_dataset" if is_dataset else "huggingface",
                "source": "huggingface",
                "full_name": data.get("id"),
                "html_url": f"https://huggingface.co/datasets/{hf_id}" if is_dataset else f"https://huggingface.co/{hf_id}",
                "description": data.get("cardData", {}).get("description", "") or "No description provided.",
                "stargazers_count": data.get("likes", 0),
                "downloads": data.get("downloads", 0),
                "tags": data.get("tags", []),
                "pushed_at": data.get("lastModified"),
            }
    except Exception as exc:
        print(f"Failed HF: {hf_id} — {exc}", file=sys.stderr)
    return None

def fetch_huggingface_search(query: str, is_dataset: bool = False) -> list[dict[str, Any]]:
    api_url = "https://huggingface.co/api/datasets" if is_dataset else "https://huggingface.co/api/models"
    params = {
        "search": query,
        "sort": "downloads",
        "direction": "-1",
        "limit": 5
    }
    try:
        response = requests.get(api_url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data:
                hf_id = item.get("id")
                results.append({
                    "type": "huggingface_dataset" if is_dataset else "huggingface",
                    "source": "huggingface",
                    "full_name": hf_id,
                    "html_url": f"https://huggingface.co/datasets/{hf_id}" if is_dataset else f"https://huggingface.co/{hf_id}",
                    "description": item.get("pipeline_tag", "No description provided."),
                    "stargazers_count": item.get("likes", 0),
                    "downloads": item.get("downloads", 0),
                    "tags": item.get("tags", []),
                    "pushed_at": item.get("lastModified"),
                })
            return results
    except Exception as exc:
        print(f"Failed HF Search: {query} — {exc}", file=sys.stderr)
    return []


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


def extract_links(markdown_text: str) -> set[tuple[str, str, str]]:
    """Returns a set of (type, url, id) tuples."""
    links = set()
    for match in GITHUB_REPO_RE.finditer(markdown_text):
        normalized = normalize_github_repo_url(match.group(0))
        if normalized:
            owner, repo = match.group(1), match.group(2)
            repo = repo.removesuffix(".git")
            links.add(("github", normalized, f"{owner}/{repo}"))
            
    for match in ARXIV_RE.finditer(markdown_text):
        links.add(("arxiv", match.group(0), match.group(1)))
        
    for match in SSRN_RE.finditer(markdown_text):
        links.add(("ssrn", match.group(0), match.group(1)))
        
    for match in HUGGINGFACE_DATASET_RE.finditer(markdown_text):
        hf_id = match.group(1)
        links.add(("huggingface_dataset", match.group(0), hf_id))

    for match in HUGGINGFACE_RE.finditer(markdown_text):
        hf_id = match.group(1)
        prefix = hf_id.split("/")[0]
        if prefix in ("datasets", "spaces", "docs", "blog", "tasks", "pricing", "models"):
            continue
        links.add(("huggingface", match.group(0), hf_id))
        
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
    if repo.get("type") == "paper":
        return False  # Do not apply repo-specific rules to papers
        
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
    if repo.get("source") == "huggingface":
        downloads = repo.get("downloads", 0) or 0
        likes = repo.get("stargazers_count", 0) or 0
        pushed_days = days_since(repo.get("pushed_at")) if repo.get("pushed_at") else 0
        recency_score = max(0.0, 1.0 - pushed_days / MAX_DAYS_SINCE_PUSH)
        return float((downloads * 0.1) + (likes * 2.0) + (recency_score * 200.0))

    if repo.get("type") == "paper":
        # Papers don't have stars. Give them a baseline score so they can be sorted by recency
        pushed_days = days_since(repo.get("pushed_at")) if repo.get("pushed_at") else 0
        recency_score = max(0.0, 1.0 - pushed_days / MAX_DAYS_SINCE_PUSH)
        boost = 200.0 if repo.get("source") == "scholar" else 0.0
        return 500.0 + recency_score * 100.0 + boost

    stars = repo.get("stargazers_count") or 0
    forks = repo.get("forks_count") or 0
    open_issues = repo.get("open_issues_count") or 0
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
    grouped["Research Papers & Articles"] = {}
    grouped["AI Models & Datasets"] = {}
    seen: set[str] = set()

    if DATA_PATH.exists():
        import json
        try:
            existing_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            for cat, items in existing_data.items():
                if cat not in grouped:
                    grouped[cat] = {}
                for repo in items:
                    url = repo.get("html_url")
                    if url:
                        grouped[cat][url] = repo
                        if repo.get("type") == "github":
                            name = repo.get("full_name")
                            if name:
                                seen.add(name)
                        else:
                            seen.add(url)
        except Exception as exc:
            print(f"Failed to load existing data: {exc}", file=sys.stderr)

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
    if not get_api_key("GITHUB_TOKEN"):
        print("Skipping seed source discovery because GITHUB_TOKEN is not set in env or api_keys.json.", file=sys.stderr)
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
            for link_type, linked_url, link_id in extract_links(readme_text):
                if link_type == "github" and linked_url == seed_normalized:
                    continue
                
                # Use a unique identifier key mapping to the type
                unique_key = f"{link_type}:{link_id}"
                if unique_key not in discovered:
                    discovered[unique_key] = {"type": link_type, "url": linked_url, "id": link_id, "count": 1}
                else:
                    discovered[unique_key]["count"] += 1
            time.sleep(1.5)

        for unique_key, item in discovered.items():
            link_type = item["type"]
            link_id = item["id"]
            repo_url = item["url"]
            
            if link_type == "github":
                if link_id in seen:
                    continue
                owner, repo = link_id.split("/")
                meta = fetch_repo_metadata(owner, repo, headers)
                time.sleep(1.0)
                if not meta or is_bad_repo(meta):
                    continue
                meta["type"] = "github"
                meta["seed_discovered"] = True
                category = classify_repo(meta)
                grouped[category][link_id] = meta
                seen.add(link_id)
            elif link_type == "arxiv":
                if link_id in seen:
                    continue
                meta = fetch_arxiv_metadata(link_id)
                time.sleep(1.0)
                if not meta:
                    continue
                meta["seed_discovered"] = True
                category = "Research Papers & Articles"
                grouped[category][repo_url] = meta
                seen.add(link_id)
            elif link_type == "ssrn":
                if link_id in seen:
                    continue
                meta = fetch_ssrn_metadata(link_id)
                time.sleep(1.0)
                if not meta:
                    continue
                meta["seed_discovered"] = True
                category = "Research Papers & Articles"
                grouped[category][repo_url] = meta
                seen.add(link_id)
            elif link_type in ("huggingface", "huggingface_dataset"):
                if link_id in seen:
                    continue
                meta = fetch_huggingface_metadata(link_id, is_dataset=(link_type == "huggingface_dataset"))
                time.sleep(1.0)
                if not meta:
                    continue
                meta["seed_discovered"] = True
                category = "AI Models & Datasets"
                grouped[category][repo_url] = meta
                seen.add(link_id)

    # 3. SerpApi Discovery
    serpapi_key = get_api_key("SERPAPI_KEY")
    if not serpapi_key:
        print("Skipping SerpApi discovery because SERPAPI_KEY is not set.", file=sys.stderr)
    else:
        keywords_path = Path("data/scholar_keywords.txt")
        if not keywords_path.exists():
            print(f"Skipping SerpApi discovery because {keywords_path} does not exist.", file=sys.stderr)
            keywords = []
        else:
            with open(keywords_path, "r", encoding="utf-8") as f:
                all_keywords = [line.strip() for line in f if line.strip()]
            if len(all_keywords) > 0:
                day_offset = dt.date.today().toordinal() % max(1, len(all_keywords) // 4)
                start_idx = day_offset * 4
                keywords = all_keywords[start_idx : start_idx + 4]
            else:
                keywords = []
        
        category = "Research Papers & Articles"
        if category in grouped:
            urls_to_remove = []
            for url, repo in grouped[category].items():
                if repo.get("search_keyword") in keywords:
                    urls_to_remove.append(url)
            for url in urls_to_remove:
                del grouped[category][url]
                if url in seen:
                    seen.remove(url)

        for kw in keywords:
            print(f"Fetching Google Scholar for: {kw}", file=sys.stderr)
            results = fetch_serpapi_scholar(kw, serpapi_key)
            for res in results:
                link = res.get("link")
                if not link:
                    continue
                if link in seen:
                    continue
                
                title = res.get("title", "Unknown Title")
                pub_info = res.get("publication_info", {}).get("summary", "")
                snippet = res.get("snippet", "")
                
                desc = f"{pub_info}. {snippet}".strip()
                desc = " ".join(desc.split())
                
                meta = {
                    "type": "paper",
                    "source": "scholar",
                    "search_keyword": kw,
                    "full_name": title,
                    "html_url": link,
                    "description": desc,
                    "pushed_at": None,
                    "seed_discovered": True,
                }
                category = "Research Papers & Articles"
                grouped[category][link] = meta
                seen.add(link)
            time.sleep(1.0)


    # 4. Hugging Face Automated Discovery
    if "keywords" in locals() and keywords:
        hf_category = "AI Models & Datasets"
        if hf_category in grouped:
            urls_to_remove = []
            for url, repo in grouped[hf_category].items():
                if repo.get("search_keyword") in keywords:
                    urls_to_remove.append(url)
            for url in urls_to_remove:
                del grouped[hf_category][url]
                if url in seen:
                    seen.remove(url)

        for kw in keywords:
            print(f"Fetching Hugging Face for: {kw}", file=sys.stderr)
            models = fetch_huggingface_search(kw, is_dataset=False)
            datasets = fetch_huggingface_search(kw, is_dataset=True)
            for res in models + datasets:
                link = res.get("html_url")
                if not link or link in seen:
                    continue
                res["search_keyword"] = kw
                res["seed_discovered"] = True
                grouped[hf_category][link] = res
                seen.add(link)
            time.sleep(1.0)

    final: dict[str, list[dict[str, Any]]] = {}
    for category, repos_by_name in grouped.items():
        repos = list(repos_by_name.values())
        repos.sort(key=repo_score, reverse=True)
        limit = 50 if category == "Research Papers & Articles" else CATEGORY_LIMIT
        final[category] = repos[:limit]

    return final


def repo_to_markdown(repo: dict[str, Any]) -> str:
    name = clean_text(repo.get("full_name"))
    url = repo.get("html_url", "")
    desc = clean_text(repo.get("description")) or "No description provided."
    
    if repo.get("source") == "huggingface":
        likes = repo.get("stargazers_count", 0) or 0
        downloads = repo.get("downloads") or 0
        pushed_at = repo.get("pushed_at")
        pushed_date = pushed_at[:10] if pushed_at else "N/A"
        return (
            f"- [{name}]({url}) — {desc} "
            f"🤗 · ❤️ {likes:,} · ⬇️ {downloads:,} · "
            f"updated {pushed_date}"
        )

    if repo.get("type") == "paper":
        pushed_at = repo.get("pushed_at")
        pushed_date = pushed_at[:10] if pushed_at else "N/A"
        date_str = f" · published {pushed_date}" if pushed_date != "N/A" else ""
        return f"- [{name}]({url}) — {desc}{date_str}"

    language = repo.get("language") or "N/A"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    pushed_at = repo.get("pushed_at")
    pushed_date = pushed_at[:10] if pushed_at else "N/A"
    license_info = repo.get("license")
    if isinstance(license_info, str):
        license_name = license_info
    else:
        license_info = license_info or {}
        license_name = license_info.get("spdx_id") or license_info.get("name") or "N/A"

    return (
        f"- [{name}]({url}) — {desc} "
        f"`{language}` · ⭐ {stars:,} · forks {forks:,} · "
        f"updated {pushed_date} · license {license_name}"
    )


def generate_readme(grouped: dict[str, list[dict[str, Any]]]) -> str:
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    contents = "\n".join(
        f"- [{category}](#{re.sub(r'[^a-z0-9 -]', '', category.lower()).replace(' ', '-')})"
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
        compact[category] = []
        for repo in repos:
            license_info = repo.get("license")
            if isinstance(license_info, str):
                license_id = license_info
            else:
                license_id = (license_info or {}).get("spdx_id")
                
            compact[category].append({
                "full_name": repo.get("full_name"),
                "type": repo.get("type", "github"),
                "source": repo.get("source"),
                "search_keyword": repo.get("search_keyword"),
                "html_url": repo.get("html_url"),
                "description": repo.get("description"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count"),
                "stargazers_count": repo.get("stargazers_count"),
                "downloads": repo.get("downloads"),
                "forks": repo.get("forks_count"),
                "pushed_at": repo.get("pushed_at"),
                "license": license_id,
                "seed_discovered": repo.get("seed_discovered"),
            })

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

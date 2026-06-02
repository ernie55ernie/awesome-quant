import re
import sys
from pathlib import Path

content = Path("scripts/update_readme.py").read_text()

# 1. Add SSRN and Hugging Face Regex
content = content.replace(
    'SSRN_RE = re.compile(\n    r"https?://papers\\.ssrn\\.com/sol3/papers\\.cfm\\?abstract_id=(\\d+)"\n)',
    'SSRN_RE = re.compile(\n    r"https?://papers\\.ssrn\\.com/sol3/papers\\.cfm\\?abstract_id=(\\d+)"\n)\nHUGGINGFACE_RE = re.compile(\n    r"https?://huggingface\\.co/([^/\\s]+/[^/\\s]+)"\n)\nHUGGINGFACE_DATASET_RE = re.compile(\n    r"https?://huggingface\\.co/datasets/([^/\\s]+/[^/\\s]+)"\n)'
)

# 2. Add HF Fetch Functions
fetch_hf_str = '''
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
'''
content = content.replace(
    'def fetch_readme_text',
    fetch_hf_str + '\n\ndef fetch_readme_text'
)

# 3. Update extract_links
links_patch = '''    for match in SSRN_RE.finditer(markdown_text):
        links.add(("ssrn", match.group(0), match.group(1)))
        
    for match in HUGGINGFACE_DATASET_RE.finditer(markdown_text):
        hf_id = match.group(1)
        links.add(("huggingface_dataset", match.group(0), hf_id))

    for match in HUGGINGFACE_RE.finditer(markdown_text):
        hf_id = match.group(1)
        prefix = hf_id.split("/")[0]
        if prefix in ("datasets", "spaces", "docs", "blog", "tasks", "pricing", "models"):
            continue
        links.add(("huggingface", match.group(0), hf_id))'''

content = content.replace(
    '    for match in SSRN_RE.finditer(markdown_text):\n        links.add(("ssrn", match.group(0), match.group(1)))',
    links_patch
)

# 4. Update collect_repositories initialization to load JSON
collect_init_orig = '''def collect_repositories() -> dict[str, list[dict[str, Any]]]:
    headers = github_headers()
    grouped: dict[str, dict[str, dict[str, Any]]] = {
        category: {} for category in CATEGORIES
    }
    seen: set[str] = set()'''

collect_init_new = '''def collect_repositories() -> dict[str, list[dict[str, Any]]]:
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
            print(f"Failed to load existing data: {exc}", file=sys.stderr)'''

content = content.replace(collect_init_orig, collect_init_new)

# 5. Add Seed Source extraction logic for HF
hf_seed_orig = '''            elif link_type == "ssrn":
                if link_id in seen:
                    continue
                meta = fetch_ssrn_metadata(link_id)
                time.sleep(1.0)
                if not meta:
                    continue
                meta["seed_discovered"] = True
                category = "Research Papers & Articles"
                grouped[category][repo_url] = meta
                seen.add(link_id)'''

hf_seed_new = hf_seed_orig + '''
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
                seen.add(link_id)'''

content = content.replace(hf_seed_orig, hf_seed_new)

# 6. Add Hugging Face Phase 4 Discovery
hf_phase4 = '''
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

    final: dict[str, list[dict[str, Any]]] = {}'''

content = content.replace('    final: dict[str, list[dict[str, Any]]] = {}', hf_phase4)

# 7. Update repo_score
repo_score_orig = '''def repo_score(repo: dict[str, Any]) -> float:
    if repo.get("type") == "paper":'''

repo_score_new = '''def repo_score(repo: dict[str, Any]) -> float:
    if repo.get("source") == "huggingface":
        downloads = repo.get("downloads", 0) or 0
        likes = repo.get("stargazers_count", 0) or 0
        pushed_days = days_since(repo.get("pushed_at")) if repo.get("pushed_at") else 0
        recency_score = max(0.0, 1.0 - pushed_days / MAX_DAYS_SINCE_PUSH)
        return float((downloads * 0.1) + (likes * 2.0) + (recency_score * 200.0))

    if repo.get("type") == "paper":'''

content = content.replace(repo_score_orig, repo_score_new)

# 8. Update repo_to_markdown
repo_md_orig = '''def repo_to_markdown(repo: dict[str, Any]) -> str:
    name = clean_text(repo.get("full_name"))
    url = repo.get("html_url", "")
    desc = clean_text(repo.get("description")) or "No description provided."
    
    if repo.get("type") == "paper":'''

repo_md_new = '''def repo_to_markdown(repo: dict[str, Any]) -> str:
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

    if repo.get("type") == "paper":'''

content = content.replace(repo_md_orig, repo_md_new)

# 9. Update save_data to persist downloads
save_orig = '''                "language": repo.get("language"),
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),'''

save_new = '''                "language": repo.get("language"),
                "stars": repo.get("stargazers_count"),
                "stargazers_count": repo.get("stargazers_count"),
                "downloads": repo.get("downloads"),
                "forks": repo.get("forks_count"),'''
content = content.replace(save_orig, save_new)


Path("scripts/update_readme.py").write_text(content)
print("Patched!")

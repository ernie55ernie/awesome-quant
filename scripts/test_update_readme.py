#!/usr/bin/env python3
"""
Test suite to verify that update_readme.py matches the intended Phase 1 behavior:
1. Ground-truth curated mappings override classification and promote cornerstone repos.
2. Blacklisted generic software libraries are strictly rejected.
3. Domain relevance validation filters out non-quant repositories (e.g. HR dashboards, generic dev tools).
4. Candidates to Review are completely purged from public README.md into internal artifacts.
5. README formatting, markdown links, and data integrity remain valid.
"""

import json
import re
import sys
from pathlib import Path

# Add repo root to sys.path
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Auto-detect local .venv site-packages if available
_venv_lib = _repo_root / ".venv" / "lib"
if _venv_lib.exists():
    for _p in _venv_lib.glob("python*/site-packages"):
        if _p.is_dir() and str(_p) not in sys.path:
            sys.path.insert(0, str(_p))

import scripts.update_readme as ur


def test_curated_mappings_loaded():
    print("[1/7] Testing curated mappings loading...")
    cat_map, seed_meta = ur.load_curated_mappings()
    assert len(cat_map) > 50, f"Expected >50 curated mappings, got {len(cat_map)}"
    
    # Cornerstone repos check
    assert cat_map.get("quantconnect/lean") == "Backtesting"
    assert cat_map.get("vnpy/vnpy") == "Research Frameworks"
    assert cat_map.get("nautechsystems/nautilus_trader") == "Execution and HFT"
    assert cat_map.get("virattt/ai-hedge-fund") == "LLM / AI Agents for Finance"
    assert cat_map.get("akfamily/akshare") == "Data and Feeds"
    assert cat_map.get("quantopian/zipline") == "Backtesting"
    
    # Check that seed metadata includes QuantConnect/Lean
    assert "quantconnect/lean" in seed_meta
    assert seed_meta["quantconnect/lean"]["stars"] >= 20000
    print("  ✓ Curated mappings loaded and verified.")


def test_blacklist_filter():
    print("[2/7] Testing explicit blacklist filter...")
    cat_map, _ = ur.load_curated_mappings()
    
    blacklisted_examples = [
        {"full_name": "pytorch/pytorch", "description": "Tensors and Dynamic neural networks", "stars": 100000},
        {"full_name": "tensorflow/tensorflow", "description": "An Open Source Machine Learning Framework", "stars": 190000},
        {"full_name": "numpy/numpy", "description": "Fundamental package for scientific computing", "stars": 30000},
        {"full_name": "pandas-dev/pandas", "description": "Flexible data analysis library", "stars": 49000},
        {"full_name": "duckdb/duckdb", "description": "Analytical in-process SQL database", "stars": 40000},
        {"full_name": "pola-rs/polars", "description": "Fast Query Engine for DataFrames", "stars": 38000},
        {"full_name": "sindresorhus/awesome", "description": "Awesome lists about all kinds of topics", "stars": 470000},
        {"full_name": "vinta/awesome-python", "description": "An opinionated list of Python frameworks", "stars": 300000},
        {"full_name": "gocolly/colly", "description": "Elegant Scraper and Crawler Framework", "stars": 25000},
        {"full_name": "iohao/ionet", "description": "A Java distributed server framework based on Aeron", "stars": 200},
    ]
    
    for repo in blacklisted_examples:
        assert ur.is_bad_repo(repo, cat_map), f"Repo {repo['full_name']} should have been rejected by blacklist!"
    print("  ✓ All blacklisted repos correctly rejected.")


def test_domain_relevance_and_negative_keywords():
    print("[3/7] Testing domain relevance & false positive filtering...")
    cat_map, _ = ur.load_curated_mappings()
    
    false_positives = [
        {
            "full_name": "Pandey-Adarsh/HR-Analytics-PowerBI",
            "description": "HR Data Analytics portfolio project on a dataset of 80K records that deals with HR KPIs like Performance tracking, attrition rate.",
            "stars": 50,
        },
        {
            "full_name": "some-user/resume-portfolio",
            "description": "My developer portfolio project showcasing web development skills.",
            "stars": 100,
        },
        {
            "full_name": "gambler/guaranteed-profit-bot",
            "description": "Binary options martingale bot with guaranteed profit",
            "stars": 50,
        },
        {
            "full_name": "generic-dev/json-parser",
            "description": "A blazing fast JSON parser written in Rust for web servers.",
            "stars": 500,
        },
    ]
    
    for repo in false_positives:
        assert ur.is_bad_repo(repo, cat_map), f"Repo {repo['full_name']} should have been rejected as non-quant/negative keyword!"
        
    # True quant repos must pass
    valid_quant = [
        {"full_name": "quant-dev/lob-toxicity", "description": "Limit order book toxicity metric calculation in high frequency trading", "stars": 150},
        {"full_name": "quant-firm/backtest-py", "description": "Vectorized backtesting engine for equity stat arb strategies", "stars": 250},
        {"full_name": "china-quant/ctp-gateway", "description": "基于上期所CTP接口的期货量化交易网关", "stars": 300},
    ]
    for repo in valid_quant:
        assert not ur.is_bad_repo(repo, cat_map), f"Valid repo {repo['full_name']} should have passed domain check!"
    print("  ✓ Domain relevance and false-positive filtering verified.")


def test_classification_and_candidates():
    print("[4/7] Testing classification logic and candidate routing...")
    cat_map, _ = ur.load_curated_mappings()
    
    # 1. Curated takes precedence
    assert ur.classify_repo({"full_name": "QuantConnect/Lean", "description": "any description"}, cat_map) == "Backtesting"
    assert ur.classify_repo({"full_name": "vnpy/vnpy", "description": "any description"}, cat_map) == "Research Frameworks"
    assert ur.classify_repo({"full_name": "virattt/ai-hedge-fund", "description": "any description"}, cat_map) == "LLM / AI Agents for Finance"
    
    # 2. Rule matching
    assert ur.classify_repo({"full_name": "user/fast-backtest", "description": "Fast event-driven backtesting library for futures"}, cat_map) == "Backtesting"
    assert ur.classify_repo({"full_name": "user/pairs-arb", "description": "Statistical arbitrage and pairs trading algorithms"}, cat_map) == "Statistical Arbitrage"
    assert ur.classify_repo({"full_name": "user/orderbook-l3", "description": "High frequency market microstructure and limit order book analytics"}, cat_map) == "Market Microstructure"
    
    # 3. Valid quant repo that does NOT match any category keyword rule becomes a Candidate to Review
    unknown_quant = {
        "full_name": "mystery/obscure-quant-asset-pricing",
        "description": "Quantitative asset pricing model implementation using novel econometric estimation techniques.",
        "stars": 100,
    }
    # If it doesn't match specific category regexes:
    # Actually 'econometric' matches Time Series. Let's make one that has only generic quant/finance signal:
    unknown_quant2 = {
        "full_name": "research/novel-quant-method",
        "description": "A novel quantitative finance methodology for analyzing asset class behaviors.",
        "stars": 100,
    }
    assert ur.is_domain_relevant(unknown_quant2, cat_map) is True
    cat = ur.classify_repo(unknown_quant2, cat_map)
    assert cat == "Candidates to Review", f"Expected 'Candidates to Review', got '{cat}'"
    print("  ✓ Classification and candidate fallback verified.")


def test_candidates_purged_from_public_readme():
    print("[5/7] Testing that Candidates to Review is excluded from public README.md...")
    readme_text = Path("README.md").read_text(encoding="utf-8")
    
    # TOC check
    assert "- [Candidates to Review]" not in readme_text, "Found Candidates to Review link in README TOC!"
    
    # Heading check
    assert "## Candidates to Review" not in readme_text, "Found ## Candidates to Review heading in README!"
    
    # Ensure github_repos.json does NOT have Candidates to Review
    data_json = json.loads(Path("data/github_repos.json").read_text(encoding="utf-8"))
    assert "Candidates to Review" not in data_json, "Found Candidates to Review in data/github_repos.json!"
    
    # Check internal artifacts exist
    assert Path("data/candidates_to_review.json").exists(), "data/candidates_to_review.json does not exist!"
    assert Path("data/candidates_to_review.md").exists(), "data/candidates_to_review.md does not exist!"
    print("  ✓ Candidates to Review completely purged from public README and saved to internal artifacts.")


def test_cornerstone_presence_and_metrics():
    print("[6/7] Testing cornerstone repositories presence and metrics in README.md...")
    readme_text = Path("README.md").read_text(encoding="utf-8")
    
    cornerstones = [
        "QuantConnect/Lean",
        "vnpy/vnpy",
        "nautechsystems/nautilus_trader",
        "virattt/ai-hedge-fund",
        "TauricResearch/TradingAgents",
        "akfamily/akshare",
        "waditu/tushare",
        "quantopian/zipline",
        "shiyu-coder/Kronos",
        "google-research/timesfm",
        "bbfamily/abu",
        "UFund-Me/Qbot",
    ]
    
    for name in cornerstones:
        assert f"[{name}]" in readme_text, f"Cornerstone repository '{name}' is missing from README.md!"
        
    # Check that QuantConnect/Lean is in Backtesting section
    backtesting_section = re.search(r"## Backtesting\n\n(.*?)(?=\n## |\Z)", readme_text, re.DOTALL)
    assert backtesting_section is not None
    assert "QuantConnect/Lean" in backtesting_section.group(1), "QuantConnect/Lean should be in ## Backtesting!"
    assert "mementum/backtrader" in backtesting_section.group(1)
    assert "quantopian/zipline" in backtesting_section.group(1)
    
    # Check that vnpy/vnpy is in Research Frameworks
    frameworks_section = re.search(r"## Research Frameworks\n\n(.*?)(?=\n## |\Z)", readme_text, re.DOTALL)
    assert frameworks_section is not None
    assert "vnpy/vnpy" in frameworks_section.group(1), "vnpy/vnpy should be in ## Research Frameworks!"
    
    # Check that virattt/ai-hedge-fund is in LLM / AI Agents
    llm_section = re.search(r"## LLM / AI Agents for Finance\n\n(.*?)(?=\n## |\Z)", readme_text, re.DOTALL)
    assert llm_section is not None
    assert "virattt/ai-hedge-fund" in llm_section.group(1), "virattt/ai-hedge-fund should be in ## LLM / AI Agents for Finance!"
    assert "TauricResearch/TradingAgents" in llm_section.group(1)
    print("  ✓ All cornerstone repositories verified in their canonical sections.")


def test_simulated_candidate_pipeline():
    print("[7/7] Testing simulated triage pipeline with newly discovered candidate...")
    cat_map, _ = ur.load_curated_mappings()
    
    # Create a simulated group containing an unclassified candidate
    mock_grouped = {
        "Backtesting": [
            {
                "full_name": "QuantConnect/Lean",
                "html_url": "https://github.com/QuantConnect/Lean",
                "description": "Lean Algorithmic Trading Engine",
                "language": "C#",
                "stars": 22526,
                "forks": 5419,
                "pushed_at": "2026-11-13T21:37:31Z",
                "license": "Apache-2.0",
            }
        ],
        "Candidates to Review": [
            {
                "full_name": "new-quant-project/novel-method",
                "html_url": "https://github.com/new-quant-project/novel-method",
                "description": "A novel quant framework that doesn't match regex rules yet",
                "language": "Python",
                "stars": 500,
                "forks": 50,
                "pushed_at": "2026-11-10T00:00:00Z",
            }
        ]
    }
    
    # Generate README from mock
    generated_readme = ur.generate_readme(mock_grouped)
    assert "Candidates to Review" not in generated_readme
    assert "new-quant-project/novel-method" not in generated_readme
    assert "QuantConnect/Lean" in generated_readme
    print("  ✓ Simulated candidate pipeline verified: candidate kept internal, excluded from README.")


if __name__ == "__main__":
    print("==================================================")
    print("Running Phase 1 Test Suite for update_readme.py...")
    print("==================================================")
    try:
        test_curated_mappings_loaded()
        test_blacklist_filter()
        test_domain_relevance_and_negative_keywords()
        test_classification_and_candidates()
        test_candidates_purged_from_public_readme()
        test_cornerstone_presence_and_metrics()
        test_simulated_candidate_pipeline()
        print("==================================================")
        print("🎉 ALL 7 TEST SUITES PASSED SUCCESSFULLY!")
        print("==================================================")
    except AssertionError as exc:
        print(f"\n❌ TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

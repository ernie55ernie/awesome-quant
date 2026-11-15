#!/usr/bin/env python3
"""
Test suite to verify that update_readme.py matches the intended Phase 1 behavior:
1. Ground-truth curated mappings override classification and promote cornerstone repos.
2. Blacklisted generic software libraries are strictly rejected.
3. Domain relevance validation filters out non-quant repositories (e.g. HR dashboards, generic dev tools).
4. Candidates to Review are completely purged from public README.md into internal artifacts.
5. README formatting, markdown links, and data integrity remain valid.
6. Hugging Face models and datasets are preserved and exempt from GitHub star thresholds.
7. Word boundary matching prevents false-positive substring leaks (optional, global, methods, programming).
8. Timezone-naive datetimes are parsed safely without offset-naive/aware TypeError.
9. Candidates are not truncated by CATEGORY_LIMIT.
"""

import json
import re
import sys
import unittest
import datetime as dt
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


class TestUpdateReadme(unittest.TestCase):

    def setUp(self):
        self.cat_map, self.seed_meta = ur.load_curated_mappings()

    def test_curated_mappings_loaded(self):
        """Verify that curated mappings include cornerstone repositories and aliases."""
        self.assertGreater(len(self.cat_map), 50)
        
        # Cornerstone repos check
        self.assertEqual(self.cat_map.get("quantconnect/lean"), "Backtesting")
        self.assertEqual(self.cat_map.get("vnpy/vnpy"), "Research Frameworks")
        self.assertEqual(self.cat_map.get("nautechsystems/nautilus_trader"), "Execution and HFT")
        self.assertEqual(self.cat_map.get("virattt/ai-hedge-fund"), "LLM / AI Agents for Finance")
        self.assertEqual(self.cat_map.get("akfamily/akshare"), "Data and Feeds")
        self.assertEqual(self.cat_map.get("quantopian/zipline"), "Backtesting")
        self.assertEqual(self.cat_map.get("nkaz001/hftbacktest"), "Execution and HFT")
        self.assertEqual(self.cat_map.get("pyportfolio/pyportfolioopt"), "Portfolio Optimization")

    def test_blacklist_filter(self):
        """Verify that general-purpose software and ML libraries are rejected."""
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
            self.assertTrue(ur.is_bad_repo(repo, self.cat_map), f"Repo {repo['full_name']} should have been rejected!")

    def test_domain_relevance_and_false_positives(self):
        """Verify domain validation rejects HR dashboards and non-financial developer projects."""
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
            self.assertTrue(ur.is_bad_repo(repo, self.cat_map), f"Repo {repo['full_name']} should have been rejected!")
            
        valid_quant = [
            {"full_name": "quant-dev/lob-toxicity", "description": "Limit order book toxicity metric calculation in high frequency trading", "stars": 150},
            {"full_name": "quant-firm/backtest-py", "description": "Vectorized backtesting engine for equity stat arb strategies", "stars": 250},
            {"full_name": "china-quant/ctp-gateway", "description": "基于上期所CTP接口的期货量化交易网关", "stars": 300},
        ]
        for repo in valid_quant:
            self.assertFalse(ur.is_bad_repo(repo, self.cat_map), f"Valid repo {repo['full_name']} should have passed domain check!")

    def test_word_boundaries_quant_keywords(self):
        """Verify word boundaries prevent substring matching leaks on eth, amm, lob, option, etc."""
        leak_cases = [
            "A fast JSON parser written in Rust with optional features and global configuration",
            "An async networking library with clean methods for python programming",
            "A variant prefix factory refactoring tool",
        ]
        for text in leak_cases:
            dummy_repo = {"full_name": "dev/utility", "description": text}
            self.assertFalse(ur.is_domain_relevant(dummy_repo, self.cat_map), f"Leak case matched: {text}")

        real_quant_cases = [
            "A fast limit order book and LOB execution engine for high-frequency trading",
            "Deploying a market making bot for BTC and ETH on Binance",
            "Options implied volatility surface modeling and pricing",
            "Multi-factor risk model and portfolio variance estimation",
        ]
        for text in real_quant_cases:
            dummy_repo = {"full_name": "quant/engine", "description": text}
            self.assertTrue(ur.is_domain_relevant(dummy_repo, self.cat_map), f"Real quant case failed: {text}")

    def test_huggingface_exempt_from_bad_repo(self):
        """Verify that Hugging Face models and datasets are not pruned due to low star counts."""
        hf_models = [
            {"type": "huggingface", "source": "huggingface", "full_name": "user/fin-model", "stars": 0, "stargazers_count": 0},
            {"type": "huggingface_dataset", "source": "huggingface", "full_name": "user/fin-dataset", "stars": 1, "stargazers_count": 1},
        ]
        for item in hf_models:
            self.assertFalse(ur.is_bad_repo(item, self.cat_map))
            self.assertEqual(ur.classify_repo(item, self.cat_map), "AI Models & Datasets")

    def test_classification_and_candidates(self):
        """Verify category rules and candidate triage fallback."""
        self.assertEqual(ur.classify_repo({"full_name": "QuantConnect/Lean", "description": "any"}, self.cat_map), "Backtesting")
        self.assertEqual(ur.classify_repo({"full_name": "vnpy/vnpy", "description": "any"}, self.cat_map), "Research Frameworks")
        self.assertEqual(ur.classify_repo({"full_name": "virattt/ai-hedge-fund", "description": "any"}, self.cat_map), "LLM / AI Agents for Finance")
        self.assertEqual(ur.classify_repo({"full_name": "nkaz001/hftbacktest", "description": "any"}, self.cat_map), "Execution and HFT")
        self.assertEqual(ur.classify_repo({"full_name": "PyPortfolio/PyPortfolioOpt", "description": "any"}, self.cat_map), "Portfolio Optimization")

        # Unclassified quant repo routes to Candidates to Review
        unknown_quant = {
            "full_name": "research/novel-quant-method",
            "description": "A novel quantitative finance methodology for analyzing asset class behaviors.",
            "stars": 100,
        }
        self.assertTrue(ur.is_domain_relevant(unknown_quant, self.cat_map))
        self.assertEqual(ur.classify_repo(unknown_quant, self.cat_map), "Candidates to Review")

    def test_rl_vs_llm_agents(self):
        """Verify that reinforcement learning repos are not misclassified as LLM agents."""
        rl_repo = {
            "full_name": "tensortrade-org/tensortrade",
            "description": "An open source reinforcement learning framework for training, evaluating, and deploying robust trading agents.",
        }
        self.assertEqual(ur.classify_repo(rl_repo, self.cat_map), "Reinforcement Learning for Trading")

        llm_repo = {
            "full_name": "virattt/ai-hedge-fund",
            "description": "An AI Hedge Fund Team powered by LLM agents.",
        }
        self.assertEqual(ur.classify_repo(llm_repo, self.cat_map), "LLM / AI Agents for Finance")

    def test_timezone_naive_datetime(self):
        """Verify that timezone-naive datetimes parse cleanly and do not crash days_since()."""
        naive_str = "2026-04-07 12:27:59"
        parsed = ur.parse_date(naive_str)
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed.tzinfo)
        # Verify days_since does not throw TypeError: can't subtract offset-naive and offset-aware datetimes
        days = ur.days_since(naive_str)
        self.assertIsInstance(days, int)

    def test_candidates_not_truncated(self):
        """Verify that Candidates to Review is not capped at CATEGORY_LIMIT (20)."""
        mock_grouped = {
            "Candidates to Review": {
                f"https://github.com/user/cand{i}": {
                    "full_name": f"user/cand{i}",
                    "stars": 100 + i,
                    "pushed_at": "2026-11-01T00:00:00Z"
                }
                for i in range(35)
            }
        }
        # Call the final grouping logic
        final = {}
        for category, repos_by_name in mock_grouped.items():
            repos = list(repos_by_name.values())
            repos.sort(key=ur.repo_score, reverse=True)
            if category in ur.INTERNAL_CATEGORIES:
                final[category] = repos
            else:
                final[category] = repos[:ur.CATEGORY_LIMIT]
                
        self.assertEqual(len(final["Candidates to Review"]), 35)

    def test_candidates_purged_from_public_readme(self):
        """Verify Candidates to Review is absent from public README and preserved internally."""
        readme_text = Path("README.md").read_text(encoding="utf-8")
        self.assertNotIn("- [Candidates to Review]", readme_text)
        self.assertNotIn("## Candidates to Review", readme_text)

        data_json = json.loads(Path("data/github_repos.json").read_text(encoding="utf-8"))
        self.assertNotIn("Candidates to Review", data_json)

        self.assertTrue(Path("data/candidates_to_review.json").exists())
        self.assertTrue(Path("data/candidates_to_review.md").exists())

    def test_cornerstone_presence_in_readme(self):
        """Verify cornerstone repos are present in public README."""
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
            "nkaz001/hftbacktest",
            "PyPortfolio/PyPortfolioOpt",
        ]
        for name in cornerstones:
            self.assertIn(f"[{name}]", readme_text)


if __name__ == "__main__":
    unittest.main()

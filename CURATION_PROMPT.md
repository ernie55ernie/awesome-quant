# Awesome Quant Curation Prompt

You are maintaining a GitHub repository called `awesome-quant`.

Goal:
Build and maintain a high-quality Awesome List of quantitative research resources, starting from GitHub repositories.

Scope:
Include resources related to:
- quantitative finance research
- alpha research
- factor modeling
- portfolio optimization
- backtesting frameworks
- market microstructure
- execution research
- high-frequency trading research
- risk modeling
- statistical arbitrage
- machine learning for trading
- crypto quant research
- academic quant finance code
- market data tools and datasets

Exclude:
- low-quality toy projects
- abandoned repos with no clear research value
- generic finance dashboards
- pure trading bots with no research framework
- get-rich-quick projects
- repos with unclear license or suspicious content
- duplicate forks unless the fork is clearly more maintained than the original

Quality criteria:
For each candidate repo, evaluate:
1. Relevance to quantitative research
2. Research depth
3. Code quality
4. Documentation quality
5. Community signal: stars, forks, issues, recent activity
6. Reproducibility: examples, notebooks, datasets, papers
7. License clarity

Output format:
Generate a clean `README.md` in Awesome List style.

Required README structure:

# Awesome Quant

A curated list of quantitative research, trading research, and market microstructure resources.

## Contents

- Research Frameworks
- Backtesting
- Alpha Research
- Portfolio Optimization
- Risk Modeling
- Market Microstructure
- Execution and HFT
- Machine Learning for Trading
- Crypto Quant
- Data and Feeds
- Academic Resources
- Interview / Learning
- LLM / AI Agents for Finance
- Utilities
- Source Lists
- Candidates to Review

For each resource, use this format:

- [repo-name](repo-url) — concise one-line description. `language`, `stars`, `last update`

Rules:
- Do not hallucinate repos.
- Do not invent stars, descriptions, licenses, or update dates.
- Only include repos from verified GitHub metadata.
- Prefer fewer high-quality entries over many weak entries.
- Keep descriptions concise and useful.
- Group each repo into the most relevant category.
- If a repo fits multiple categories, place it in the most useful category and avoid duplication.
- Put uncertain repos into a final section called “Candidates to Review”.
- Add a generation timestamp at the bottom.

## Seed Sources

Use the following GitHub repositories as seed sources for discovering quantitative research resources:

- https://github.com/0voice/Awesome-QuantDev-Learn
- https://github.com/je-suis-tm/quant-trading
- https://github.com/grananqvist/Awesome-Quant-Machine-Learning-Trading
- https://github.com/thuquant/awesome-quant
- https://github.com/wilsonfreitas/awesome-quant
- https://github.com/georgezouq/awesome-ai-in-finance
- https://github.com/zhanghaitao1/awesome-quant-papers
- https://github.com/goex-top/awesome-go-quant
- https://github.com/wangzhe3224/awesome-systematic-trading
- https://github.com/leoncuhk/awesome-quant-ai
- https://github.com/paperswithbacktest/awesome-systematic-trading
- https://github.com/learn-crypto-trading/learn-crypto-trading.github.io
- https://github.com/rchardzhu/awesome-quant-cn
- https://github.com/dMLTquant/dMLTresearch
- https://github.com/SoYuCry/awesome-quant-interview
- https://github.com/Tom-roujiang/Awesome-LLM-Quantitative-Trading-Papers
- https://github.com/staskh/awesome-math-and-trading
- https://github.com/sia-zhang/awesome-quant
- https://github.com/The-Swarm-Corporation/awesome-financial-agents
- https://github.com/mrtnrocks/awesome-developer-finance

Instructions:

1. Treat these repositories as discovery sources, not automatically approved final entries.
2. Read their README files and extract linked GitHub repositories, papers, books, datasets, courses, and tools.
3. Normalize all GitHub links into canonical `https://github.com/{owner}/{repo}` format.
4. Remove duplicate links.
5. For every GitHub repository candidate, fetch or verify metadata:
   - repository name
   - URL
   - description
   - stars
   - forks
   - primary language
   - license
   - last pushed date
   - archived/fork status
6. Do not hallucinate metadata.
7. Do not copy descriptions blindly from source awesome lists. Rewrite concise neutral descriptions based on verified repo metadata and README context.
8. Classify each resource into the most appropriate category:
   - Research Frameworks
   - Backtesting
   - Alpha Research
   - Portfolio Optimization
   - Risk Modeling
   - Market Microstructure
   - Execution and HFT
   - Machine Learning for Trading
   - Crypto Quant
   - Data and Feeds
   - Academic Resources
   - Interview / Learning
   - LLM / AI Agents for Finance
   - Utilities
9. Add the seed awesome-list repositories themselves into a section called `Source Lists`.
10. Keep provenance internally:
    - track which seed source discovered each resource
    - if a resource appears in multiple seed sources, increase its priority
11. Prefer resources that appear in multiple reputable lists, are actively maintained, or have strong research value.
12. Put weak, stale, or uncertain resources into `Candidates to Review` instead of the main list.
13. Exclude:
    - signal-selling projects
    - pure trading bots without research value
    - abandoned low-quality repos
    - duplicate forks
    - suspicious or unclear projects
    - content without quantitative research relevance

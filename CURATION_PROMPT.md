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
- Utilities

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

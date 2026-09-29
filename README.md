# eBay Market & Price Intelligence Scraper

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Headless%20Automation-green?logo=playwright&logoColor=white)
![WAF Evasion](https://img.shields.io/badge/WAF%20Evasion-Akamai%20Edge-red)
![Architecture](https://img.shields.io/badge/Architecture-Asynchronous-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

[🇷🇺 Читать на русском](README_RU.md)

---

An enterprise-grade, asynchronous e-commerce intelligence scraper designed to extract real-time product listings, pricing data, shipping fees, and item conditions from eBay.

Built from the ground up to bypass enterprise-grade anti-bot security layers (Akamai Edge WAF) without relying on expensive residential proxies.

### Key Architectural Highlights
- **Akamai WAF Evasion:** Full human cadence emulation using real Chrome channel binaries, dynamic GDPR consent resolution, and progressive scroll simulation to satisfy browser telemetry listeners.
- **DOM Resilience:** Universal parser engineered to handle both legacy (`.s-item`) and modern A/B test (`.s-card`) eBay listing structures.
- **Automated Data Persistence:** Validates and dumps datasets simultaneously into analysis-ready `.csv` and `.json` formats.
- **Configurable Search Pipelines:** Accepts keyword-based search queries as well as direct pre-filtered marketplace URLs via environment variables.

### Tech Stack
- **Python 3.12**
- **Playwright** (Automated browser runtime)
- **BeautifulSoup4** (DOM parsing engine)
- **python-dotenv** (Environment configuration)

### Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium

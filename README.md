# Ghemex

**Ghemex** is a CTI and OSINT tool designed to analyze public GitHub repositories and commit history to identify email addresses exposed through commit metadata.

Unlike basic API checks, it uses advanced techniques such as exhaustive branch/tag scraping and deep extraction via raw `.patch` files to recover identities that are often hidden from the standard web interface.

---

## Features

- **Automated Enumeration**
  Full mapping of a target's public repositories using efficient API pagination.

- **Multithreaded Analysis**
  Uses `ThreadPoolExecutor` to speed up scanning across large datasets.

- **Obfuscation Bypass**
  Extracts emails from `From:` headers inside raw commit `.patch` files.

- **Rate Limit Handling**
  Detects GitHub API limits (403/401) and applies automatic backoff to avoid bans.

- **Deduplication**
  Filters out generic GitHub emails (e.g. `noreply.github.com`) and keeps only unique results.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/intelshadow/ghemex.git
cd ghemex
```

Install dependencies:

```bash
pip install requests
```

---

## Requirements

- Python 3.6+
- requests>=2.28.0
- A GitHub Personal Access Token (PAT) is optional for small targets

---

## Usage

```bash
python ghemex.py <username> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `username` | Target GitHub username (required) |
| `-t`, `--token` | GitHub Personal Access Token |
| `-w`, `--workers` | Number of threads (default: 10) |
| `--full` | Scan all branches and tags |
| `--deep` | Deep scraping via raw `.patch` headers |

> A token is not required for targets with few repositories when running without `--full` or `--deep`. For larger targets or intensive scans, a token is strongly recommended to avoid hitting the unauthenticated API rate limit (60 req/hour).

---

## Examples

Basic scan (no token needed for small targets):

```bash
python ghemex.py targetuser
```

Authenticated scan with full branch and tag coverage:

```bash
python ghemex.py targetuser -t ghp_yourtoken --full
```

Full deep scan:

```bash
python ghemex.py targetuser -t ghp_yourtoken --full --deep -w 15
```

---

## Disclaimer

This tool is intended for educational purposes.
Use it only on accounts you own or have explicit written permission to analyze. The author is not responsible for any misuse or damage caused by this tool.
Always comply with GitHub's Terms of Service and applicable laws.

---

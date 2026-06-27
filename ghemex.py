#!/usr/bin/env python3

import requests
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import RequestException

RED = '\033[91m'
RESET = '\033[0m'

BANNER = r"""

 ▄▀▀▀▀▀▀▀▀▀█ █▀▀▀▀█ ▓▀▀▀█  ▄▀▀▀▀▀▀▀▀▀█ █▀▀▀▀▀▀▀▀▀▄▀▀▀▀▀▄   ▄▀▀▀▀▀▀▀▀▀█ █▀▀▀▀█ ▓▀▀▀█
█·   ▄▄▄▄▄▄█ ▀    ▓ ▒ ∙ █ █·   ▄▄▄▄▄▄█ ▀    ▄▄     ▄    █ █·   ▄▄▄▄▄▄█ ▀    ▓ ▒ ∙ █
▓  . ▓ ▄▄▄▄▄ ▓    ▓▄░   ▓ ▓  . ▓▄▄▄▄▄▄ ▓    ▓ ▌   ▓ ▌   ▓ ▓  . ▓▄▄▄▄▄▄ ▓    ▓▄░   ▓
▒ ∙  ▒ ▄   ▒ ▒   ·▄▄▄   ▒ ▒ ∙  ▄▄▄▄▄▄▒ ▒    ▒ ▒ · ▒ ▒ · ▒ ▒ ∙  ▄▄▄▄▄▄▒  ▄▀ ·▄▄▄  ▀▄
░    ░▄░   ░ ░ .  ░ ░  .░ ░    ░▄▄▄▄▄▄ ░   ∙░ ░   ░ ░   ░ ░    ░▄▄▄▄▄▄ ░ .  ░ ░  .░
█    .    ·█ █    █ █∙  █ █    .    ·█ █ ∙  █ █   █ █   █ █    .    ·█ █    █ █∙  █
█▄▄▄▄▄▄▄▄▄▄█ █▄▄▄▄█ █▄▄▄█ █▄▄▄▄▄▄▄▄▄▄█ █▄▄▄▄█ █▄▄▄█ █▄▄▄█ █▄▄▄▄▄▄▄▄▄▄█ █▄▄▄▄█ █▄▄▄█

                          --- GitHub Email Extractor --- 
"""

class GitHubAPIClient:
    def __init__(self, token=None):
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "GHEmailFinder-PRO/3.0"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    def request(self, url, params=None, is_patch=False):
        "calculate remaining rate limits and pauses execution to prevent IP bans"
        try:
            r = self.session.get(url, params=params, timeout=15)
            
            if not is_patch and r.status_code in (401, 403):
                remaining = int(r.headers.get("X-RateLimit-Remaining", 0))
                if remaining == 0:
                    reset_timestamp = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                    sleep_time = max(reset_timestamp - int(time.time()), 0) + 1
                    print(f"\n[!] API rate limit exceeded. Backing off for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    return self.request(url, params, is_patch)
                else:
                    print(f"\n[!] API error (HTTP {r.status_code}). Verify your token.")
                    sys.exit(1)

            if r.status_code == 200:
                return r.text if is_patch else r.json()
                
        except RequestException:
            pass

        return None


class GHEmailFinder:
    "repository mapping, commit parsing, and data deduplication"
    def __init__(self, username, token=None, workers=10, full_scan=False, deep_scan=False):
        self.username = username
        self.workers = workers
        self.full_scan = full_scan
        self.deep_scan = deep_scan
        self.api = GitHubAPIClient(token)
        self.results = []

    def get_repos(self):
        "Retrieves all public repositories for the user via pagination."
        repos = []
        page = 1
        while True:
            data = self.api.request(
                f"https://api.github.com/users/{self.username}/repos",
                params={"per_page": 100, "page": page, "type": "all"}
            )
            if not data:
                break
            
            repos.extend(data)
            
            if len(data) < 100:
                break
                            
            page += 1
        return repos

    def get_refs(self, repo):
        "Collects all branches and tags if full_scan is enabled."
        if not self.full_scan:
            return [None]

        refs = []
        branches = self.api.request(f"https://api.github.com/repos/{self.username}/{repo}/branches", {"per_page": 100})
        if branches:
            refs.extend([b["name"] for b in branches])

        tags = self.api.request(f"https://api.github.com/repos/{self.username}/{repo}/tags", {"per_page": 100})
        if tags:
            refs.extend([t["name"] for t in tags])

        return refs if refs else [None]

    def extract_patch_email(self, repo, sha):
        """
        Extracts the 'From:' header from the commit's .patch file to bypass basic GitHub obfuscation.
        """
        url = f"https://github.com/{self.username}/{repo}/commit/{sha}.patch"
        text_data = self.api.request(url, is_patch=True)
        
        if text_data:
            for line in text_data.splitlines():
                if line.startswith("From:") and "<" in line:
                    email = line.split("<")[1].split(">")[0]
                    if "noreply.github.com" not in email:
                        return email
        return None

    def analyze_repo(self, repo):
        "Iterates through commit history, caches evaluated SHAs to prevent redundant API calls and extracts identities"
        findings = []
        seen_shas = set()
        refs = self.get_refs(repo)

        for ref in refs:
            page = 1
            while True:
                params = {"per_page": 100, "page": page}
                if ref:
                    params["sha"] = ref
                    
                commits = self.api.request(
                    f"https://api.github.com/repos/{self.username}/{repo}/commits",
                    params=params
                )
                
                if not commits or not isinstance(commits, list):
                    break

                for c in commits:
                    sha = c.get("sha")
                    # Skip previously analyzed commits across different branches
                    if not sha or sha in seen_shas:
                        continue
                        
                    seen_shas.add(sha)
                    
                    commit_data = c.get("commit", {})
                    author = commit_data.get("author", {})
                    email = author.get("email")

                    # Primary extraction (API payload)
                    if email and "noreply.github.com" not in email:
                        findings.append({
                            "email": email,
                            "repo": repo
                        })

                    # Secondary extraction (Raw Patch Headers)
                    if self.deep_scan:
                        patch_email = self.extract_patch_email(repo, sha)
                        if patch_email and patch_email != email:
                            findings.append({
                                "email": patch_email,
                                "repo": repo
                            })
                
                if len(commits) < 100:
                    break
                
                page += 1
        return findings

    def run(self):
        "Main execution flow and concurrent job management"
        print(f"[*] Enumerating repositories for target: {self.username}")
        repos = self.get_repos()
        
        if not repos:
            print("[-] No accessible repositories found.")
            return

        print(f"[+] {len(repos)} repositories discovered.")
        print((f"\n[+] Extracting  emails..."))
        
        if self.deep_scan:
            print("[!] Extracting .patch headers...")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            jobs = [executor.submit(self.analyze_repo, r["name"]) for r in repos]
            for job in as_completed(jobs):
                self.results.extend(job.result())

        unique_emails = set([r["email"] for r in self.results])

        print("\n" + "-" * 50)
        print("[*] Enumeration results:")
        print("-" * 50)

        for email in sorted(unique_emails):
            print(f"\n[+] {RED}{email}{RESET}")
            repos_involved = sorted(list(set([r["repo"] for r in self.results if r["email"] == email])))
            for repo in repos_involved:
                print(f"- Source: {repo}")
        print(f"\n[*] Total unique addresses identified: {len(unique_emails)}")


def main():
    print(BANNER)
    parser = argparse.ArgumentParser(description="A CTI tool for extracting emails from GitHub.")
    parser.add_argument("username", help="Target GitHub username")
    parser.add_argument("-t", "--token", help="GitHub personal access token")
    parser.add_argument("-w", "--workers", default=10, type=int, help="Number of threads")
    parser.add_argument("--full", action="store_true", help="Scan all branches and tags")
    parser.add_argument("--deep", action="store_true", help="Perform deep scraping on .patch files")

    args = parser.parse_args()
    tool = GHEmailFinder(args.username, args.token, args.workers, args.full, args.deep)

    try:
        tool.run()
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()

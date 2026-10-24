#!/usr/bin/env python3
"""
Sanitize an n8n workflow export before publishing it.

Usage:
    python scripts/sanitize_workflow.py raw-export.json workflow/automate-blogs-and-social-media-posts.json

What it does:
  - keeps only name, nodes, connections and settings
  - removes the error-workflow link and instance-specific ids
  - replaces credential ids and names with placeholders
  - replaces Google Sheet / Drive ids, LinkedIn person id and e-mail addresses
  - removes webhook ids and cached Google URLs
Then it scans the result and prints anything that still looks like a secret or id.
"""
import json
import re
import sys

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LONG_ID = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{25,}(?![A-Za-z0-9_-])")
SUSPICIOUS = ["tvly-", "Bearer ", "EAA", "sk-", "AIza", "access_token\": \"", "client_secret"]

FOLDERS = {
    "Create Blog Doc": "YOUR_BLOG_DOCS_FOLDER_ID",
    "Create Twitter Doc": "YOUR_TWITTER_DOCS_FOLDER_ID",
    "Create YouTube Script Doc": "YOUR_YOUTUBE_DOCS_FOLDER_ID",
}


def clean_rl(key, value):
    """Resource-locator fields such as documentId / sheetName."""
    if not (isinstance(value, dict) and value.get("__rl")):
        return value
    name = value.get("cachedResultName")
    value.pop("cachedResultUrl", None)
    if key == "documentId":
        value["mode"] = "id"
        value["value"] = "YOUR_GOOGLE_SHEET_ID"
        value.pop("cachedResultName", None)
    elif key == "sheetName" and name:
        value["mode"] = "name"
        value["value"] = name
    return value


def clean_node(node):
    node.pop("webhookId", None)
    params = node.get("parameters", {})
    for key in list(params):
        params[key] = clean_rl(key, params[key])
    if "folderId" in params:
        params["folderId"] = FOLDERS.get(node.get("name"), "YOUR_DRIVE_FOLDER_ID")
    if "person" in params:
        params["person"] = "YOUR_LINKEDIN_PERSON_ID"
    if "sendTo" in params:
        params["sendTo"] = "your-approver@example.com"
    creds = node.get("credentials")
    if creds:
        for cred_type in creds:
            creds[cred_type] = {"id": "REPLACE_ME", "name": "Your " + cred_type}
    return node


def scrub_strings(obj):
    """Replace any remaining e-mail address inside any string."""
    if isinstance(obj, dict):
        return {k: scrub_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_strings(v) for v in obj]
    if isinstance(obj, str):
        return EMAIL.sub(
            lambda m: m.group(0) if m.group(0).endswith("@example.com") else "your-approver@example.com",
            obj,
        )
    return obj


def scan(obj, path=""):
    findings = []
    if "/credentials/" in path:
        return findings
    if isinstance(obj, dict):
        for k, v in obj.items():
            findings += scan(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            findings += scan(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for m in LONG_ID.finditer(obj):
            token = m.group(0)
            if token.startswith(("YOUR_", "REPLACE_")) or "_" in token and token.isupper():
                continue
            if not any(c.isdigit() for c in token):
                continue  # plain names have no digits, real Google ids do
            if token.count("-") >= 4 and len(token) == 36:  # node id UUID
                continue
            findings.append((path, "long id-like token", token))
        for s in SUSPICIOUS:
            if s in obj:
                findings.append((path, "suspicious text", s))
        for e in EMAIL.findall(obj):
            if not e.endswith("@example.com"):
                findings.append((path, "e-mail address", e))
    return findings


def main(src, dst):
    with open(src, encoding="utf-8") as f:
        raw = json.load(f)
    out = {
        "name": raw.get("name", "Workflow"),
        "nodes": [clean_node(n) for n in raw.get("nodes", [])],
        "connections": raw.get("connections", {}),
        "settings": {k: v for k, v in raw.get("settings", {}).items() if k != "errorWorkflow"},
    }
    out = scrub_strings(out)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    findings = scan(out)
    print(f"Wrote {dst} ({len(out['nodes'])} nodes).")
    if findings:
        print("\nREVIEW THESE BEFORE PUBLISHING:")
        for path, kind, text in findings:
            print(f"  {kind}: {text}   at {path}")
        sys.exit(1)
    print("Scan found no ids, e-mails or key-like text. Still open the file and search for 'token' and 'secret'.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])

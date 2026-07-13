"""Structural Diff — Detect what changed in a web page's DOM structure.

Unlike simple text diff, this understands HTML structure:
which elements were added, removed, moved, or changed.

Usage:
    differ = StructuralDiff()
    differ.capture(html, url="https://example.com")
    # ... later ...
    differ.capture(new_html, url="https://example.com")
    diff = differ.diff()
    print(diff)  # {'added': [...], 'removed': [...], 'changed': [...]}
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag


def _element_signature(tag: Tag) -> dict:
    """Extract structural signature of an HTML element."""
    path = []
    parent = tag.parent
    while parent and parent.name:
        path.append(parent.name)
        parent = parent.parent

    attrs = {}
    for key in ("class", "id", "role", "data-testid", "aria-label", "name", "type"):
        val = tag.get(key)
        if val:
            if isinstance(val, list):
                val = " ".join(val)
            attrs[key] = val

    return {
        "tag": tag.name,
        "path": "/".join(reversed(path)),
        "attrs": attrs,
        "text_preview": tag.get_text(strip=True)[:100],
        "child_count": len(list(tag.children)),
    }


def _extract_structure(html: str) -> list[dict]:
    """Extract DOM structure signatures from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    elements = []
    # Focus on semantic/meaningful elements
    selectors = [
        "div",
        "section",
        "article",
        "nav",
        "header",
        "footer",
        "aside",
        "main",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
        "tr",
        "td",
        "ul",
        "ol",
        "li",
        "p",
        "span",
        "a",
        "img",
        "button",
        "form",
        "input",
        "select",
        "label",
    ]

    for tag_name in selectors:
        for tag in soup.find_all(tag_name):
            sig = _element_signature(tag)
            # Skip generic divs with no identifying attributes
            if tag_name == "div" and not sig["attrs"] and not sig["text_preview"]:
                continue
            sig["_hash"] = hashlib.md5(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:8]
            elements.append(sig)

    return elements


def _find_added(old: list[dict], new: list[dict]) -> list[dict]:
    """Find elements present in new but not in old."""
    old_hashes = {e["_hash"] for e in old}
    return [e for e in new if e["_hash"] not in old_hashes]


def _find_removed(old: list[dict], new: list[dict]) -> list[dict]:
    """Find elements present in old but not in new."""
    new_hashes = {e["_hash"] for e in new}
    return [e for e in old if e["_hash"] not in new_hashes]


def _find_changed(old: list[dict], new: list[dict]) -> list[dict]:
    """Find elements whose text content changed."""
    changes = []
    old_by_sig = {}
    for e in old:
        key = f"{e['tag']}:{e['path']}:{json.dumps(e['attrs'], sort_keys=True)}"
        old_by_sig[key] = e

    for e in new:
        key = f"{e['tag']}:{e['path']}:{json.dumps(e['attrs'], sort_keys=True)}"
        if key in old_by_sig and old_by_sig[key]["text_preview"] != e["text_preview"]:
            changes.append(
                {
                    "tag": e["tag"],
                    "path": e["path"],
                    "attrs": e["attrs"],
                    "old_text": old_by_sig[key]["text_preview"],
                    "new_text": e["text_preview"],
                }
            )
    return changes


def _generate_summary(added: list, removed: list, changed: list) -> str:
    """Human-readable summary of structural changes."""
    parts = []
    if added:
        parts.append(f"Added {len(added)} element(s)")
        for e in added[:3]:
            label = e.get("attrs", {}).get("id") or e.get("attrs", {}).get("class") or e["tag"]
            parts.append(f"  + <{e['tag']}> ({label})")
    if removed:
        parts.append(f"Removed {len(removed)} element(s)")
        for e in removed[:3]:
            label = e.get("attrs", {}).get("id") or e.get("attrs", {}).get("class") or e["tag"]
            parts.append(f"  - <{e['tag']}> ({label})")
    if changed:
        parts.append(f"Changed {len(changed)} element(s)")
        for e in changed[:3]:
            parts.append(f'  ~ <{e["tag"]}>: "{e["old_text"][:50]}" → "{e["new_text"][:50]}"')
    if not parts:
        return "No structural changes detected"
    return "\n".join(parts)


class StructuralDiff:
    """Track and compare web page DOM structure over time.

    Stores snapshots locally and produces structural diffs showing
    which elements were added, removed, or changed.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "~/.harvest/diffs").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots: dict[str, list[dict]] = {}

    def _url_id(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _snapshot_path(self, url: str) -> Path:
        return self.data_dir / f"{self._url_id(url)}.json"

    def capture(self, html: str, url: str = "") -> list[dict]:
        """Capture DOM structure from HTML.

        Returns the extracted structure list.
        """
        structure = _extract_structure(html)
        if url:
            # Save to disk
            path = self._snapshot_path(url)
            with open(path, "w") as f:
                json.dump({"url": url, "structure": structure}, f)
            self._snapshots[url] = structure
        return structure

    def load_snapshot(self, url: str) -> Optional[list[dict]]:
        """Load a previously saved snapshot from disk."""
        path = self._snapshot_path(url)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        structure = data.get("structure", [])
        self._snapshots[url] = structure
        return structure

    def diff(
        self,
        old_html: Optional[str] = None,
        new_html: Optional[str] = None,
        url: str = "",
    ) -> dict:
        """Compare two HTML snapshots and produce a structural diff.

        If old_html/new_html are provided, extracts structure on the fly.
        Otherwise, compares the two most recent captures.
        """
        if old_html and new_html:
            old_structure = _extract_structure(old_html)
            new_structure = _extract_structure(new_html)
        elif url:
            saved = self.load_snapshot(url)
            if saved is None:
                return {"error": f"No snapshot found for {url}"}
            new_structure = self._snapshots.get(url, saved)
            old_structure = saved
        else:
            return {"error": "Provide html pairs or a url with saved snapshots"}

        added = _find_added(old_structure, new_structure)
        removed = _find_removed(old_structure, new_structure)
        changed = _find_changed(old_structure, new_structure)

        summary = _generate_summary(added, removed, changed)

        return {
            "url": url,
            "added": added[:20],
            "removed": removed[:20],
            "changed": changed[:20],
            "summary": summary,
            "old_count": len(old_structure),
            "new_count": len(new_structure),
        }

    def history(self, url: str) -> list[dict]:
        """Get saved snapshot info for a URL."""
        path = self._snapshot_path(url)
        if not path.exists():
            return []
        with open(path) as f:
            return [json.load(f)]

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Bump NetWORKS core version for release.

Updates manifest.json (version, version_string, version_info, build_date, release_notes)
and CHANGELOG.md (converts [Unreleased] to versioned entry or adds minimal entry).

Usage:
  python scripts/bump_version.py [patch|minor|major]
  Default: patch

Environment:
  BUMP_TYPE: patch|minor|major (overrides CLI arg)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "manifest.json")
CHANGELOG_PATH = os.path.join(REPO_ROOT, "CHANGELOG.md")

# Pattern for versioned CHANGELOG entries: ## [X.Y.Z] - YYYY-MM-DD
CHANGELOG_VERSION_RE = re.compile(r"^## \[([\d.]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
# Pattern for [Unreleased] section
UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)


def _parse_version(version_str: str) -> tuple:
    """Parse version string to (major, minor, patch)."""
    parts = version_str.strip().split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return major, minor, patch


def _bump_version(current: str, bump_type: str) -> str:
    """Bump version string by type (patch, minor, major)."""
    major, minor, patch = _parse_version(current)
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    # patch (default)
    return f"{major}.{minor}.{patch + 1}"


def _extract_release_notes_from_changelog(changelog_content: str, new_version: str) -> str:
    """
    Extract release notes for the new version.
    Prefer [Unreleased] content; otherwise use a minimal default.
    """
    # Look for ## [Unreleased] and capture until next ##
    unreleased_match = re.search(
        r"^## \[Unreleased\]\s*\n(.*?)(?=^## \[|\Z)",
        changelog_content,
        re.MULTILINE | re.DOTALL,
    )
    if unreleased_match:
        body = unreleased_match.group(1).strip()
        if body:
            # Use first ~200 chars as summary for manifest.release_notes
            lines = body.split("\n")
            summary_lines = []
            for line in lines:
                if line.strip().startswith("###"):
                    summary_lines.append(line.strip())
                elif line.strip() and not summary_lines:
                    summary_lines.append(line.strip())
                elif summary_lines and line.strip():
                    summary_lines.append(line.strip())
                if len("\n".join(summary_lines)) > 300:
                    break
            return "\n".join(summary_lines).strip() or f"Release {new_version}."
    return f"Release {new_version}."


def _update_changelog(changelog_content: str, new_version: str) -> str:
    """
    Update CHANGELOG: convert [Unreleased] to [X.Y.Z] with today's date,
    or add a minimal versioned entry at the top. Skip if version already exists.
    """
    if f"## [{new_version}]" in changelog_content:
        return changelog_content

    today = datetime.utcnow().strftime("%Y-%m-%d")

    if UNRELEASED_RE.search(changelog_content):
        # Replace ## [Unreleased] with ## [X.Y.Z] - date
        new_content = UNRELEASED_RE.sub(
            f"## [{new_version}] - {today}",
            changelog_content,
            count=1,
        )
        return new_content

    # No [Unreleased]; add minimal entry after the header/description
    header_end = changelog_content.find("\n## ")
    if header_end == -1:
        header_end = len(changelog_content)

    insert_pos = changelog_content.find("\n## [", 1)
    if insert_pos == -1:
        insert_pos = header_end

    new_entry = (
        f"\n## [{new_version}] - {today}\n\n"
        f"### Changed\n"
        f"- Version bump to {new_version}\n\n"
    )
    return changelog_content[:insert_pos] + new_entry + changelog_content[insert_pos:]


def run(bump_type: str = "patch") -> str:
    """
    Bump version, update manifest and CHANGELOG. Returns new version string.
    """
    bump_type = (os.environ.get("BUMP_TYPE") or bump_type).lower()
    if bump_type not in ("patch", "minor", "major"):
        bump_type = "patch"

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    current = manifest.get("version", "0.0.0")
    new_version = _bump_version(current, bump_type)
    major, minor, patch = _parse_version(new_version)
    build = manifest.get("version_info", {}).get("build", 0) + 1
    build_date = datetime.utcnow().strftime("%Y-%m-%d")

    with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
        changelog = f.read()

    release_notes = _extract_release_notes_from_changelog(changelog, new_version)
    changelog_updated = _update_changelog(changelog, new_version)

    manifest["version"] = new_version
    manifest["version_string"] = new_version
    manifest["version_info"] = {
        "major": major,
        "minor": minor,
        "patch": patch,
        "build": build,
    }
    manifest["build_date"] = build_date
    manifest["release_notes"] = release_notes

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        f.write(changelog_updated)

    return new_version


def main():
    parser = argparse.ArgumentParser(description="Bump NetWORKS core version for release")
    parser.add_argument(
        "bump_type",
        nargs="?",
        default="patch",
        choices=["patch", "minor", "major"],
        help="Version bump type (default: patch)",
    )
    args = parser.parse_args()
    new_version = run(args.bump_type)
    print(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())

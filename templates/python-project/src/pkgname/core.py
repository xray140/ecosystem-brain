"""Core logic for the pkgname package."""

from __future__ import annotations

import re


def slugify(text: str) -> str:
    """Return a kebab-case slug (lowercase; spaces/underscores -> hyphens).

    Mirrors the ecosystem file-naming rule: kebab-case, no spaces, no uppercase.
    """
    text = re.sub(r"[\s_]+", "-", text.strip().lower())
    text = re.sub(r"[^a-z0-9-]", "", text)
    return re.sub(r"-{2,}", "-", text).strip("-")

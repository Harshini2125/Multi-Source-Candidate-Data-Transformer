"""Skill canonicalization.

Maps surface forms / synonyms to a single canonical skill name
(``"js"`` -> ``"JavaScript"``). Unknown skills are *title-cased and kept*, never
dropped and never invented into something else — an unrecognised skill is still
real information.
"""

from __future__ import annotations

from typing import Optional

# canonical name -> list of synonyms / surface forms (all lowercased on lookup)
_SYNONYMS: dict[str, list[str]] = {
    "JavaScript": ["js", "javascript", "ecmascript", "java script"],
    "TypeScript": ["ts", "typescript"],
    "Python": ["python", "py", "python3"],
    "Java": ["java"],
    "Go": ["go", "golang"],
    "C++": ["c++", "cpp", "cplusplus"],
    "C#": ["c#", "csharp", "c sharp"],
    "React": ["react", "react.js", "reactjs"],
    "Node.js": ["node", "node.js", "nodejs"],
    "PostgreSQL": ["postgres", "postgresql", "psql"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongo", "mongodb"],
    "Docker": ["docker"],
    "Kubernetes": ["k8s", "kubernetes", "kube"],
    "AWS": ["aws", "amazon web services"],
    "Machine Learning": ["ml", "machine learning"],
    "SQL": ["sql"],
    "REST": ["rest", "rest api", "restful"],
    "GraphQL": ["graphql", "gql"],
    "Git": ["git"],
}

# Flattened lookup: synonym -> canonical
_LOOKUP: dict[str, str] = {
    syn: canonical for canonical, syns in _SYNONYMS.items() for syn in syns
}


def canonicalize_skill(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key:
        return None
    if key in _LOOKUP:
        return _LOOKUP[key]
    # Unknown skill: keep it, normalised to a stable title case.
    return str(raw).strip()

"""
The scope taxonomy for Jarvis's memory. Every entry is classified into
exactly one of five scopes, broadest to narrowest:

  - global       System-wide, or something that cuts across multiple
                 companies, or concerns the structure of Jarvis itself.
                 Prefer this over guessing a single company whenever a
                 memory's relevance clearly isn't limited to one business.
  - organization Spans the user's whole business portfolio (multiple
                 companies) without being system-structural — overarching
                 practices, preferences, and facts about how the user runs
                 their businesses in general. Also the default bucket when
                 no company is active and nothing else applies.
  - company      Specific to exactly one Company workspace.
  - project      Specific to one Project (a discrete unit of work Jarvis is
                 helping with) — narrower than company. A Project isn't
                 itself tied to a company in the schema, so a project-scoped
                 memory may optionally also carry a company_id.
  - personal     About the user as an individual, not business at all.

`global`, `organization`, and `personal` are never tied to a company or
project — a company_id/project_id passed alongside one of those is simply
not applicable and is dropped, not treated as an error (this keeps the
resolver forgiving of upstream defaults like chat.py's "fill in the active
company" behavior, which doesn't know what scope the caller ended up
choosing). `company` requires a company_id; `project` requires a
project_id.

Classifying content semantically — recognizing that a note mentions two
companies, or is about Jarvis's own configuration rather than the business
— is the chat model's job, not this module's. See the `remember` tool's
description in app.core.agent_tools for the guidance Jarvis follows at
runtime, including when to ask the user instead of guessing. This module
only enforces internal consistency and provides the deterministic default
for callers that never reason about content at all (e.g. auto-captured
chat turns, or the manual "Add Memory" form).
"""
from app.exceptions import ValidationError

MEMORY_SCOPES = ["global", "organization", "company", "project", "personal"]

_COMPANY_LESS_SCOPES = {"global", "organization", "personal"}


def resolve_scope(
    *,
    scope: str | None,
    company_id: str | None,
    project_id: str | None,
) -> tuple[str, str | None, str | None]:
    """Validates/normalizes (scope, company_id, project_id) into a
    consistent triple, raising ValidationError only when a *required* field
    is genuinely missing (e.g. scope='company' with no company_id) — never
    for an extra field that scope doesn't use, which is just dropped.
    """
    if scope is None:
        if project_id:
            scope = "project"
        elif company_id:
            scope = "company"
        else:
            scope = "organization"

    if scope not in MEMORY_SCOPES:
        raise ValidationError(f"Unknown memory scope '{scope}'. Valid: {', '.join(MEMORY_SCOPES)}")

    if scope in _COMPANY_LESS_SCOPES:
        return scope, None, None

    if scope == "company":
        if not company_id:
            raise ValidationError("scope='company' requires a company_id.")
        return scope, company_id, None

    # scope == "project"
    if not project_id:
        raise ValidationError("scope='project' requires a project_id.")
    return scope, company_id, project_id

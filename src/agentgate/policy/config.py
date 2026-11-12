from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from agentgate.models import Role, StrictModel


class RolePolicy(StrictModel):
    tools: set[str] = Field(default_factory=set)
    file_prefixes: list[str] = Field(default_factory=list)
    db_tables: dict[str, set[str]] = Field(default_factory=dict)
    db_direct_limit: int = 0
    db_hard_limit: int = 0
    mail_domains: set[str] = Field(default_factory=set)


class PolicyConfig(StrictModel):
    version: str
    roles: dict[Role, RolePolicy]
    sensitive_patterns: list[str] = Field(default_factory=list)
    mail_requires_approval: bool = True

    @classmethod
    def from_json(cls, path: str | Path) -> "PolicyConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)


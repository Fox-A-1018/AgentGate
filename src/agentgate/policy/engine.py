from __future__ import annotations

import re

from agentgate.models import (
    Decision,
    NormalizedToolCall,
    PolicyDecision,
    ReasonCode,
    RiskLevel,
)

from .config import PolicyConfig


class PolicyEngine:
    def __init__(self, config: PolicyConfig) -> None:
        self.config = config
        self.version = config.version
        self._sensitive_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config.sensitive_patterns]

    def evaluate(self, call: NormalizedToolCall) -> PolicyDecision:
        role_policy = self.config.roles.get(call.role)
        if role_policy is None or call.tool_name not in role_policy.tools:
            return self._decision(
                Decision.DENY,
                ReasonCode.TOOL_NOT_ALLOWED,
                f"role {call.role.value} cannot use {call.tool_name}",
                RiskLevel.HIGH,
                "rbac.tool_permission",
            )
        if call.tool_name == "file.read":
            return self._evaluate_file(call, role_policy.file_prefixes)
        if call.tool_name == "db.select":
            return self._evaluate_db(call, role_policy)
        if call.tool_name == "mail.send":
            return self._evaluate_mail(call, role_policy.mail_domains)
        return self._decision(
            Decision.DENY,
            ReasonCode.UNKNOWN_TOOL,
            f"no policy evaluator for {call.tool_name}",
            RiskLevel.HIGH,
            "policy.unknown_tool",
        )

    def _evaluate_file(self, call: NormalizedToolCall, prefixes: list[str]) -> PolicyDecision:
        path = call.parameters["path"]
        allowed = any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)
        if not allowed:
            return self._decision(
                Decision.DENY,
                ReasonCode.RESOURCE_OUT_OF_SCOPE,
                "file path is outside the role's allowed prefixes",
                RiskLevel.HIGH,
                "file.allowed_prefix",
            )
        return self._decision(
            Decision.ALLOW,
            ReasonCode.ALLOWED,
            "file path is authorized",
            RiskLevel.LOW,
            "file.allowed_prefix",
        )

    def _evaluate_db(self, call: NormalizedToolCall, role_policy) -> PolicyDecision:
        table = call.parameters["table"]
        fields = set(call.parameters["fields"])
        filters = set(call.parameters["filters"])
        allowed_fields = role_policy.db_tables.get(table)
        if allowed_fields is None or not fields.issubset(allowed_fields) or not filters.issubset(allowed_fields):
            return self._decision(
                Decision.DENY,
                ReasonCode.RESOURCE_OUT_OF_SCOPE,
                "database table, fields, or filters exceed the role's scope",
                RiskLevel.HIGH,
                "db.table_field_allowlist",
            )
        limit = call.parameters["limit"]
        if limit > role_policy.db_hard_limit:
            return self._decision(
                Decision.DENY,
                ReasonCode.HARD_LIMIT_EXCEEDED,
                "database row limit exceeds the hard limit",
                RiskLevel.CRITICAL,
                "db.hard_limit",
            )
        if limit > role_policy.db_direct_limit:
            return self._decision(
                Decision.REQUIRE_APPROVAL,
                ReasonCode.APPROVAL_REQUIRED,
                "database row limit exceeds the direct-execution threshold",
                RiskLevel.HIGH,
                "db.soft_limit",
            )
        return self._decision(
            Decision.ALLOW,
            ReasonCode.ALLOWED,
            "database request is authorized",
            RiskLevel.LOW,
            "db.table_field_allowlist",
        )

    def _evaluate_mail(self, call: NormalizedToolCall, allowed_domains: set[str]) -> PolicyDecision:
        domains = {address.rsplit("@", 1)[1] for address in call.parameters["recipients"]}
        if not domains.issubset(allowed_domains):
            return self._decision(
                Decision.DENY,
                ReasonCode.RESOURCE_OUT_OF_SCOPE,
                "one or more recipient domains are not allowed",
                RiskLevel.CRITICAL,
                "mail.recipient_domain",
            )
        content = call.parameters["subject"] + "\n" + call.parameters["body"]
        if any(pattern.search(content) for pattern in self._sensitive_patterns):
            return self._decision(
                Decision.DENY,
                ReasonCode.SENSITIVE_DATA_DETECTED,
                "message content matches a sensitive-data pattern",
                RiskLevel.CRITICAL,
                "mail.sensitive_content",
            )
        if self.config.mail_requires_approval:
            return self._decision(
                Decision.REQUIRE_APPROVAL,
                ReasonCode.APPROVAL_REQUIRED,
                "simulated outbound messages require human approval",
                RiskLevel.HIGH,
                "mail.human_approval",
            )
        return self._decision(
            Decision.ALLOW,
            ReasonCode.ALLOWED,
            "simulated outbound message is authorized",
            RiskLevel.MEDIUM,
            "mail.recipient_domain",
        )

    def _decision(
        self,
        decision: Decision,
        reason_code: ReasonCode,
        reason: str,
        risk_level: RiskLevel,
        matched_rule: str,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=decision,
            reason_code=reason_code,
            reason=reason,
            risk_level=risk_level,
            matched_rule=matched_rule,
            policy_version=self.version,
        )


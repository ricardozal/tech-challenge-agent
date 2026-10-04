"""Versioned business policy (R-14): policy/policy.yaml is current, policy/archive/*.yaml are older."""

from pathlib import Path

import yaml

from actions_api.policy_model import Policy

__all__ = ["Policy", "PolicyRegistry", "PolicyUnavailable"]


class PolicyUnavailable(LookupError):
    pass


class PolicyRegistry:
    def __init__(self, current: Policy, by_version: dict[str, Policy]):
        self._current = current
        self._by_version = by_version

    @classmethod
    def load(cls, policy_dir: Path) -> "PolicyRegistry":
        current = _read(policy_dir / "policy.yaml")
        by_version = {current.policy_version: current}
        for path in sorted((policy_dir / "archive").glob("*.yaml")):
            archived = _read(path)
            by_version.setdefault(archived.policy_version, archived)
        return cls(current, by_version)

    def current(self) -> Policy:
        return self._current

    def get(self, version: str) -> Policy:
        try:
            return self._by_version[version]
        except KeyError:
            raise PolicyUnavailable(version) from None

    def versions(self) -> list[str]:
        return sorted(self._by_version)


def _read(path: Path) -> Policy:
    with path.open(encoding="utf-8") as fh:
        return Policy.model_validate(yaml.safe_load(fh))

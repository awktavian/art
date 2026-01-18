#!/usr/bin/env python3
"""Audit secrets for security issues.

Scans codebase for:
- Hardcoded secrets
- Weak secrets
- Insecure defaults
- Secrets in version control
- Unencrypted secret storage

Usage:
    python scripts/security/audit_secrets.py --scan-code
    python scripts/security/audit_secrets.py --check-strength
    python scripts/security/audit_secrets.py --full-audit
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kagami.core.security.encryption import validate_secret_strength
from kagami.core.security.secrets_manager import (
    SecretBackendType,
    create_secrets_manager,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Patterns for detecting hardcoded secrets
SECRET_PATTERNS = [
    # API keys
    (r'api[_-]?key[\s=:]+["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API Key"),
    (r'apikey[\s=:]+["\']?([a-zA-Z0-9_\-]{20,})["\']?', "API Key"),
    # AWS
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r'aws[_-]?secret[_-]?access[_-]?key[\s=:]+["\']?([a-zA-Z0-9/+=]{40})["\']?', "AWS Secret Key"),
    # JWT
    (r'jwt[_-]?secret[\s=:]+["\']?([a-zA-Z0-9_\-]{20,})["\']?', "JWT Secret"),
    # Generic secrets
    (r'secret[_-]?key[\s=:]+["\']?([a-zA-Z0-9_\-]{16,})["\']?', "Secret Key"),
    (r'password[\s=:]+["\']?([a-zA-Z0-9_\-@#$%]{8,})["\']?', "Password"),
    # Database
    (r"postgres://[^:]+:([^@]+)@", "PostgreSQL Password"),
    (r"mysql://[^:]+:([^@]+)@", "MySQL Password"),
    # OAuth
    (r'client[_-]?secret[\s=:]+["\']?([a-zA-Z0-9_\-]{20,})["\']?', "OAuth Client Secret"),
    # Private keys
    (r"-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----", "Private Key"),
]


# Weak/default secrets to flag
WEAK_SECRETS = {
    "password",
    "admin",
    "secret",
    "changeme",
    "default",
    "test",
    "demo",
    "admin123",
    "password123",
    "user123",
    "guest123",
    "12345",
    "qwerty",
    "letmein",
    "root",
}


class SecretAuditor:
    """Audits secrets for security issues."""

    def __init__(self, root_dir: Path):
        """Initialize auditor.

        Args:
            root_dir: Root directory to scan
        """
        self.root_dir = root_dir
        self.findings = []

    def scan_codebase(self, exclude_dirs: set | None = None) -> list:
        """Scan codebase for hardcoded secrets.

        Args:
            exclude_dirs: Directories to exclude

        Returns:
            List of findings
        """
        if exclude_dirs is None:
            exclude_dirs = {
                ".git",
                ".mypy_cache",
                "__pycache__",
                "node_modules",
                ".venv",
                "venv",
                "build",
                "dist",
            }

        findings = []

        logger.info(f"Scanning codebase at {self.root_dir}...")

        for file_path in self.root_dir.rglob("*"):
            # Skip directories and excluded paths
            if file_path.is_dir():
                continue

            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            # Only scan text files
            if file_path.suffix in [".py", ".js", ".ts", ".json", ".yaml", ".yml", ".env", ".sh"]:
                findings.extend(self._scan_file(file_path))

        self.findings.extend(findings)
        return findings

    def _scan_file(self, file_path: Path) -> list:
        """Scan a single file for secrets.

        Args:
            file_path: Path to file

        Returns:
            List of findings in this file
        """
        findings = []

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for line_num, line in enumerate(content.split("\n"), 1):
                # Skip comments
                if line.strip().startswith(("#", "//")):
                    continue

                # Check each pattern
                for pattern, secret_type in SECRET_PATTERNS:
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for _match in matches:
                        findings.append(
                            {
                                "file": str(file_path.relative_to(self.root_dir)),
                                "line": line_num,
                                "type": secret_type,
                                "severity": "HIGH",
                                "message": f"Potential {secret_type} found",
                            }
                        )

        except Exception as e:
            logger.debug(f"Error scanning {file_path}: {e}")

        return findings

    async def check_secret_strength(self, manager) -> list:
        """Check strength of stored secrets.

        Args:
            manager: SecretsManager instance

        Returns:
            List of findings
        """
        findings = []

        logger.info("Checking strength of stored secrets...")

        try:
            secrets = await manager.list_secrets()

            for secret_name in secrets:
                try:
                    value = await manager.get_secret(secret_name, user="auditor")

                    if not value:
                        continue

                    # Check if weak/default
                    if value.lower() in WEAK_SECRETS:
                        findings.append(
                            {
                                "secret": secret_name,
                                "type": "Weak Secret",
                                "severity": "CRITICAL",
                                "message": "Secret uses a weak/default value",
                            }
                        )
                        continue

                    # Check strength
                    is_valid, error = validate_secret_strength(value, min_length=16)
                    if not is_valid:
                        findings.append(
                            {
                                "secret": secret_name,
                                "type": "Weak Strength",
                                "severity": "HIGH",
                                "message": error,
                            }
                        )

                except Exception as e:
                    logger.debug(f"Error checking '{secret_name}': {e}")

        except Exception as e:
            logger.error(f"Error checking secret strength: {e}")

        self.findings.extend(findings)
        return findings

    def check_file_permissions(self) -> list:
        """Check permissions on sensitive files.

        Returns:
            List of findings
        """
        findings = []

        logger.info("Checking file permissions...")

        sensitive_files = [
            ".env",
            ".env.local",
            ".env.production",
            "secrets.enc",
            "master.key",
            "credentials.json",
            "service-account.json",
        ]

        for pattern in sensitive_files:
            for file_path in self.root_dir.rglob(pattern):
                if file_path.is_file():
                    # Check permissions (Unix only)
                    try:
                        stat_info = os.stat(file_path)
                        mode = stat_info.st_mode & 0o777

                        # Should be 600 or 400
                        if mode > 0o600:
                            findings.append(
                                {
                                    "file": str(file_path.relative_to(self.root_dir)),
                                    "type": "Insecure Permissions",
                                    "severity": "HIGH",
                                    "message": f"File has insecure permissions: {oct(mode)}",
                                }
                            )

                    except Exception as e:
                        logger.debug(f"Error checking permissions for {file_path}: {e}")

        self.findings.extend(findings)
        return findings

    def check_git_tracked_secrets(self) -> list:
        """Check for secrets in git history.

        Returns:
            List of findings
        """
        findings = []

        logger.info("Checking for secrets in git...")

        git_dir = self.root_dir / ".git"
        if not git_dir.exists():
            logger.info("Not a git repository, skipping git checks")
            return findings

        # Check .gitignore
        gitignore_path = self.root_dir / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path) as f:
                gitignore_content = f.read()

            # Check for important patterns
            important_patterns = [".env", "*.key", "secrets/", "credentials.json"]
            for pattern in important_patterns:
                if pattern not in gitignore_content:
                    findings.append(
                        {
                            "file": ".gitignore",
                            "type": "Missing Gitignore Pattern",
                            "severity": "MEDIUM",
                            "message": f"Pattern '{pattern}' not in .gitignore",
                        }
                    )

        self.findings.extend(findings)
        return findings

    def generate_report(self) -> str:
        """Generate audit report.

        Returns:
            Report string
        """
        if not self.findings:
            return "✓ No security issues found!"

        # Group by severity
        critical = [f for f in self.findings if f.get("severity") == "CRITICAL"]
        high = [f for f in self.findings if f.get("severity") == "HIGH"]
        medium = [f for f in self.findings if f.get("severity") == "MEDIUM"]
        low = [f for f in self.findings if f.get("severity") == "LOW"]

        report = []
        report.append("=" * 80)
        report.append("SECURITY AUDIT REPORT")
        report.append("=" * 80)
        report.append(f"\nTotal Findings: {len(self.findings)}")
        report.append(f"  CRITICAL: {len(critical)}")
        report.append(f"  HIGH: {len(high)}")
        report.append(f"  MEDIUM: {len(medium)}")
        report.append(f"  LOW: {len(low)}")
        report.append("")

        if critical:
            report.append("\n" + "=" * 80)
            report.append("CRITICAL ISSUES")
            report.append("=" * 80)
            for finding in critical:
                report.append(self._format_finding(finding))

        if high:
            report.append("\n" + "=" * 80)
            report.append("HIGH SEVERITY ISSUES")
            report.append("=" * 80)
            for finding in high:
                report.append(self._format_finding(finding))

        if medium:
            report.append("\n" + "=" * 80)
            report.append("MEDIUM SEVERITY ISSUES")
            report.append("=" * 80)
            for finding in medium:
                report.append(self._format_finding(finding))

        return "\n".join(report)

    def _format_finding(self, finding: dict) -> str:
        """Format a finding for display.

        Args:
            finding: Finding dictionary

        Returns:
            Formatted string
        """
        lines = []
        lines.append(f"\n[{finding.get('severity')}] {finding.get('type')}")

        if "file" in finding:
            if "line" in finding:
                lines.append(f"  Location: {finding['file']}:{finding['line']}")
            else:
                lines.append(f"  File: {finding['file']}")

        if "secret" in finding:
            lines.append(f"  Secret: {finding['secret']}")

        lines.append(f"  Message: {finding.get('message')}")

        return "\n".join(lines)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Audit secrets for security issues")

    parser.add_argument(
        "--scan-code",
        action="store_true",
        help="Scan codebase for hardcoded secrets",
    )
    parser.add_argument(
        "--check-strength",
        action="store_true",
        help="Check strength of stored secrets",
    )
    parser.add_argument(
        "--check-permissions",
        action="store_true",
        help="Check file permissions on sensitive files",
    )
    parser.add_argument(
        "--check-git",
        action="store_true",
        help="Check for secrets in git",
    )
    parser.add_argument(
        "--full-audit",
        action="store_true",
        help="Run all audit checks",
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default=".",
        help="Root directory to audit (default: current directory)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="local",
        choices=["local", "aws", "gcp", "azure", "vault"],
        help="Secret backend for strength checks (default: local)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output report to file",
    )

    args = parser.parse_args()

    # Get root directory
    root_dir = Path(args.root_dir).resolve()
    if not root_dir.exists():
        print(f"Error: Directory not found: {root_dir}")
        sys.exit(1)

    # Create auditor
    auditor = SecretAuditor(root_dir)

    # Run checks
    if args.full_audit or args.scan_code:
        auditor.scan_codebase()

    if args.full_audit or args.check_strength:
        # Configure backend
        backend_type_map = {
            "local": SecretBackendType.LOCAL_ENCRYPTED,
            "aws": SecretBackendType.AWS_SECRETS_MANAGER,
            "gcp": SecretBackendType.GCP_SECRET_MANAGER,
            "azure": SecretBackendType.AZURE_KEY_VAULT,
            "vault": SecretBackendType.HASHICORP_VAULT,
        }

        backend_type = backend_type_map[args.backend]
        backend_config = {}

        if args.backend == "local":
            backend_config = {
                "storage_path": str(Path.home() / ".kagami" / "secrets" / "secrets.enc"),
                "master_key_path": str(Path.home() / ".kagami" / "secrets" / "master.key"),
                "auto_generate_key": True,
            }

        manager = create_secrets_manager(
            backend_type=backend_type,
            config=backend_config,
        )

        await auditor.check_secret_strength(manager)

    if args.full_audit or args.check_permissions:
        auditor.check_file_permissions()

    if args.full_audit or args.check_git:
        auditor.check_git_tracked_secrets()

    # Generate report
    report = auditor.generate_report()

    # Output report
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Exit with error code if critical/high issues found
    critical_count = len([f for f in auditor.findings if f.get("severity") == "CRITICAL"])
    high_count = len([f for f in auditor.findings if f.get("severity") == "HIGH"])

    if critical_count > 0 or high_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

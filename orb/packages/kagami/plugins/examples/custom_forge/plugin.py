"""Document Generator Plugin - Custom Forge module for document generation.

This plugin demonstrates creating a custom Forge module that generates
various types of technical documentation.

Capabilities:
- Generate API documentation
- Create architecture diagrams
- Generate deployment guides
- Create user manuals
- Integration with Forge matrix

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.plugins.base import BasePlugin, HealthCheckResult, PluginMetadata
from kagami.plugins.hooks import HookContext, HookType, get_hook_registry

logger = logging.getLogger(__name__)


class DocumentGeneratorModule:
    """Custom Forge module for document generation."""

    def __init__(self):
        """Initialize document generator module."""
        self._documents_generated = 0
        self._supported_formats = ["markdown", "html", "pdf", "docx"]

    def generate(
        self, doc_type: str, content: dict[str, Any], format: str = "markdown"
    ) -> dict[str, Any]:
        """Generate a document.

        Args:
            doc_type: Type of document (api_docs, architecture, deployment, manual)
            content: Document content specification
            format: Output format (markdown, html, pdf, docx)

        Returns:
            Generated document data
        """
        if format not in self._supported_formats:
            raise ValueError(f"Unsupported format: {format}")

        self._documents_generated += 1

        # Generate document based on type
        if doc_type == "api_docs":
            return self._generate_api_docs(content, format)
        elif doc_type == "architecture":
            return self._generate_architecture_doc(content, format)
        elif doc_type == "deployment":
            return self._generate_deployment_guide(content, format)
        elif doc_type == "manual":
            return self._generate_user_manual(content, format)
        else:
            raise ValueError(f"Unknown document type: {doc_type}")

    def _generate_api_docs(self, content: dict[str, Any], format: str) -> dict[str, Any]:
        """Generate API documentation."""
        endpoints = content.get("endpoints", [])

        # Generate markdown content
        doc_content = "# API Documentation\n\n"
        for endpoint in endpoints:
            doc_content += f"## {endpoint['method']} {endpoint['path']}\n\n"
            doc_content += f"{endpoint.get('description', 'No description')}\n\n"

            if "parameters" in endpoint:
                doc_content += "### Parameters\n\n"
                for param in endpoint["parameters"]:
                    doc_content += (
                        f"- `{param['name']}` ({param['type']}): {param['description']}\n"
                    )
                doc_content += "\n"

            if "responses" in endpoint:
                doc_content += "### Responses\n\n"
                for code, desc in endpoint["responses"].items():
                    doc_content += f"- **{code}**: {desc}\n"
                doc_content += "\n"

        return {
            "type": "api_docs",
            "format": format,
            "content": doc_content,
            "metadata": {
                "endpoints_documented": len(endpoints),
                "generated_at": "2025-12-28",
            },
        }

    def _generate_architecture_doc(self, content: dict[str, Any], format: str) -> dict[str, Any]:
        """Generate architecture documentation."""
        components = content.get("components", [])
        connections = content.get("connections", [])

        doc_content = "# System Architecture\n\n"
        doc_content += "## Components\n\n"
        for component in components:
            doc_content += f"### {component}\n\n"
            doc_content += "Component description goes here.\n\n"

        doc_content += "## Connections\n\n"
        for conn in connections:
            doc_content += f"- {conn['from']} → {conn['to']}\n"

        return {
            "type": "architecture",
            "format": format,
            "content": doc_content,
            "metadata": {
                "components": len(components),
                "connections": len(connections),
            },
        }

    def _generate_deployment_guide(self, content: dict[str, Any], format: str) -> dict[str, Any]:
        """Generate deployment guide."""
        steps = content.get("steps", [])

        doc_content = "# Deployment Guide\n\n"
        for i, step in enumerate(steps, 1):
            doc_content += f"## Step {i}: {step['title']}\n\n"
            doc_content += f"{step['description']}\n\n"

            if "commands" in step:
                doc_content += "```bash\n"
                for cmd in step["commands"]:
                    doc_content += f"{cmd}\n"
                doc_content += "```\n\n"

        return {
            "type": "deployment",
            "format": format,
            "content": doc_content,
            "metadata": {"steps": len(steps)},
        }

    def _generate_user_manual(self, content: dict[str, Any], format: str) -> dict[str, Any]:
        """Generate user manual."""
        sections = content.get("sections", [])

        doc_content = "# User Manual\n\n"
        for section in sections:
            doc_content += f"## {section['title']}\n\n"
            doc_content += f"{section['content']}\n\n"

        return {
            "type": "manual",
            "format": format,
            "content": doc_content,
            "metadata": {"sections": len(sections)},
        }

    def get_stats(self) -> dict[str, Any]:
        """Get module statistics."""
        return {
            "documents_generated": self._documents_generated,
            "supported_formats": self._supported_formats,
        }


class DocumentGeneratorPlugin(BasePlugin):
    """Plugin that adds document generation to Forge."""

    def __init__(self):
        """Initialize plugin."""
        super().__init__()
        self._module: DocumentGeneratorModule | None = None
        self._hook_registry = get_hook_registry()

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            plugin_id="kagami.document_generator",
            name="Document Generator",
            version="1.0.0",
            description="Custom Forge module for technical document generation",
            author="Kagami Team",
            entry_point="kagami.plugins.examples.custom_forge.plugin:DocumentGeneratorPlugin",
            dependencies=[],
            capabilities=["forge_module", "document_generation"],
            kagami_version_min="0.1.0",
            kagami_version_max="999.0.0",
            tags=["forge", "documents", "generation"],
        )

    def on_init(self) -> None:
        """Initialize plugin."""
        logger.info("Initializing Document Generator plugin")

        # Create module
        self._module = DocumentGeneratorModule()

        # Register Forge hooks
        self._hook_registry.register_hook(
            HookType.MODULE_REGISTRATION,
            self._handle_module_registration,
            plugin_id=self.get_metadata().plugin_id,
        )

        self._hook_registry.register_hook(
            HookType.PRE_GENERATION,
            self._pre_generation,
            plugin_id=self.get_metadata().plugin_id,
        )

        self._hook_registry.register_hook(
            HookType.POST_GENERATION,
            self._post_generation,
            plugin_id=self.get_metadata().plugin_id,
        )

    def on_start(self) -> None:
        """Start plugin."""
        logger.info("Document Generator module active")

        # Register with Forge registry (if available)
        try:
            # Note: This is a simplified example. In a real implementation,
            # you would need to extend ComponentRegistry to support plugins.
            logger.info("Document generator ready for document creation")

        except Exception as e:
            logger.warning(f"Could not register with Forge: {e}")

    def on_stop(self) -> None:
        """Stop plugin."""
        logger.info("Document Generator paused")

    def on_cleanup(self) -> None:
        """Cleanup plugin resources."""
        logger.info("Cleaning up Document Generator plugin")

        # Unregister hooks
        self._hook_registry.unregister_hook(
            HookType.MODULE_REGISTRATION,
            self.get_metadata().plugin_id,
        )
        self._hook_registry.unregister_hook(
            HookType.PRE_GENERATION,
            self.get_metadata().plugin_id,
        )
        self._hook_registry.unregister_hook(
            HookType.POST_GENERATION,
            self.get_metadata().plugin_id,
        )

        self._module = None

    def health_check(self) -> HealthCheckResult:
        """Check plugin health."""
        if self._module is None:
            return HealthCheckResult(
                healthy=False,
                status="error",
                details={"error": "Module not initialized"},
            )

        stats = self._module.get_stats()
        return HealthCheckResult(
            healthy=True,
            status="ok",
            details={
                "documents_generated": stats["documents_generated"],
                "supported_formats": len(stats["supported_formats"]),
            },
        )

    def _handle_module_registration(self, ctx: HookContext) -> HookContext:
        """Handle module registration hook."""
        logger.debug("Document generator module registration hook called")
        return ctx

    def _pre_generation(self, ctx: HookContext) -> HookContext:
        """Pre-generation hook.

        Args:
            ctx: Hook context

        Returns:
            Modified context
        """
        # Check if this is a document generation request
        generation_type = ctx.get("type", "")
        if "document" in generation_type.lower() or "docs" in generation_type.lower():
            ctx.set("document_generation", True)
            logger.debug("Document generation request detected")

        return ctx

    def _post_generation(self, ctx: HookContext) -> HookContext:
        """Post-generation hook.

        Args:
            ctx: Hook context

        Returns:
            Modified context
        """
        if ctx.get("document_generation"):
            logger.debug("Document generation completed")

        return ctx

    def get_module(self) -> DocumentGeneratorModule | None:
        """Get the document generator module.

        Returns:
            Document generator module instance
        """
        return self._module


__all__ = ["DocumentGeneratorModule", "DocumentGeneratorPlugin"]

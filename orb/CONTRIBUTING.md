# Contributing to Kagami

Welcome to the Kagami project! This guide will help you contribute effectively to the Kagami codebase while maintaining our high standards for quality and safety.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Code Review Process](#code-review-process)

## Code of Conduct

By participating in this project, you agree to maintain a respectful, inclusive, and harassment-free environment for everyone. We expect:

- Respectful communication and constructive feedback
- Welcoming diverse perspectives and experiences
- Focusing on what's best for the community
- Showing empathy toward other community members

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- Git with LFS support
- Docker and docker-compose (for local services)
- Make (for build automation)

### Development Setup

1. **Fork and Clone**
   ```bash
   git fork https://github.com/KagamiOS/Kagami
   git clone https://github.com/YOUR_USERNAME/Kagami
   cd Kagami
   ```

2. **Initialize Submodules**
   ```bash
   git submodule update --init --recursive
   ```

3. **Set Up Development Environment**
   ```bash
   make setup
   # Or manually:
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

4. **Start Local Services**
   ```bash
   docker-compose up -d
   ```

5. **Verify Installation**
   ```bash
   make test-tier-1
   ```

## Development Workflow

### Branch Naming

Use descriptive branch names following this convention:

- `feature/` - New features (e.g., `feature/audio-streaming`)
- `fix/` - Bug fixes (e.g., `fix/memory-leak-training`)
- `docs/` - Documentation only (e.g., `docs/api-reference`)
- `refactor/` - Code refactoring (e.g., `refactor/split-large-orchestrator`)
- `test/` - Test additions/fixes (e.g., `test/forge-integration`)
- `chore/` - Maintenance tasks (e.g., `chore/update-dependencies`)

### Creating a Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

## Coding Standards

### Python Style

We follow **PEP 8** with some modifications:

- **Line length**: 88 characters (Black default)
- **Imports**: Organized in 3 groups (stdlib, third-party, local)
- **Type hints**: Required for all public functions
- **Docstrings**: Required for all public modules, classes, and functions

### Code Quality Tools

All code must pass these checks:

```bash
make lint        # Ruff linting
make typecheck   # mypy type checking
make format      # Black formatting
```

### Type Hints

All functions must have type hints:

```python
# Good ✅
def process_input(data: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Process input with timeout."""
    ...

# Bad ❌
def process_input(data, timeout=5.0):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_safety(context: dict) -> SafetyResult:
    """
    Calculate safety score using Control Barrier Function.

    Args:
        context: Dictionary containing state and action information
            - state: Current system state
            - action: Proposed action
            - history: Past trajectory

    Returns:
        SafetyResult with:
            - h_value: Safety barrier value (must be >= 0)
            - safe: Boolean indicating if action is safe
            - confidence: Confidence in assessment (0-1)

    Raises:
        SafetyViolationError: If h_value < 0 and action cannot be modified

    Example:
        >>> result = calculate_safety({"state": state, "action": action})
        >>> assert result.safe
    """
    ...
```

## Testing Requirements

### Test Coverage

- **Minimum coverage**: 70% for new code
- **Critical paths**: 90%+ coverage required
- **Safety systems**: 100% coverage required

### Test Structure

Organize tests by type:

```
tests/
├── unit/           # Fast unit tests (<1s each)
├── integration/    # Integration tests (<5s each)
├── e2e/           # End-to-end tests (<60s each)
└── performance/   # Performance benchmarks
```

### Writing Tests

```python
import pytest
from kagami.core import Component

class TestComponent:
    """Test suite for Component class."""

    @pytest.fixture
    def component(self):
        """Provide test component."""
        return Component(config={"test": True})

    def test_basic_operation(self, component):
        """Test that basic operation works correctly."""
        result = component.process("test")
        assert result.success
        assert result.data == "processed: test"

    @pytest.mark.asyncio
    async def test_async_operation(self, component):
        """Test asynchronous operations."""
        result = await component.process_async("test")
        assert result.success
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test tier
make test-tier-1    # Unit tests only
make test-tier-2    # Unit + integration

# Run specific test file
pytest tests/unit/test_component.py

# Run with coverage
pytest --cov=kagami --cov-report=html
```

## Documentation

### Code Documentation

- All public APIs must have docstrings
- Complex algorithms need inline comments
- Include usage examples in docstrings

### Documentation Files

Update relevant documentation when making changes:

- **README.md** - For major feature additions
- **docs/API.md** - For API changes
- **docs/ARCHITECTURE.md** - For architectural changes
- **CHANGELOG.md** - For all changes (see below)

### Changelog Updates

Add entries to `CHANGELOG.md` under `[Unreleased]`:

```markdown
## [Unreleased]

### Added
- New audio streaming endpoint for real-time voice synthesis (#123)

### Changed
- Improved safety checking performance by 40% (#124)

### Fixed
- Memory leak in training orchestrator (#125)

### Security
- Added rate limiting to authentication endpoints (#126)
```

## Pull Request Process

### Before Submitting

1. ✅ All tests pass (`make test`)
2. ✅ Code is formatted (`make format`)
3. ✅ Linting passes (`make lint`)
4. ✅ Type checking passes (`make typecheck`)
5. ✅ Documentation is updated
6. ✅ CHANGELOG.md is updated
7. ✅ Commit messages follow guidelines

### Submitting a Pull Request

1. **Push your branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Go to GitHub and create a PR
   - Use the PR template
   - Link related issues
   - Add clear description of changes

3. **PR Title Format**
   ```
   [Category] Brief description

   Examples:
   - [Feature] Add audio streaming endpoint
   - [Fix] Resolve memory leak in training
   - [Docs] Update API documentation
   - [Test] Add integration tests for Forge
   ```

4. **PR Description Template**
   ```markdown
   ## Summary
   Brief description of what this PR does.

   ## Motivation
   Why is this change needed? What problem does it solve?

   ## Changes
   - Change 1
   - Change 2
   - Change 3

   ## Testing
   How was this tested?
   - [ ] Unit tests added/updated
   - [ ] Integration tests added/updated
   - [ ] Manual testing performed

   ## Checklist
   - [ ] Tests pass
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated
   - [ ] Type hints added
   - [ ] Backwards compatible (or breaking change documented)

   ## Related Issues
   Closes #123
   Related to #124
   ```

## Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation only
- **style**: Formatting, missing semicolons, etc.
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

### Examples

```bash
# Feature
feat(audio): add real-time streaming endpoint

Implements WebSocket-based audio streaming for voice synthesis.
Includes rate limiting and authentication.

Closes #123

# Bug fix
fix(training): resolve memory leak in orchestrator

The training orchestrator was not properly cleaning up GPU memory
between epochs, causing OOM errors on long training runs.

Fixes #124

# Documentation
docs(api): update authentication examples

Added examples for API key and JWT authentication.

# Breaking change
feat(safety)!: require h(x) >= 0.1 threshold

BREAKING CHANGE: Safety threshold increased from 0.0 to 0.1
for additional safety margin. Update safety configs accordingly.
```

## Code Review Process

### For Contributors

- Respond to feedback promptly
- Be open to suggestions
- Ask questions if feedback is unclear
- Update PR based on review comments

### Review Timeline

- **Initial review**: Within 2 business days
- **Follow-up review**: Within 1 business day
- **Approval**: Requires 1-2 approvals depending on scope

### What Reviewers Look For

1. **Correctness**: Does the code work as intended?
2. **Tests**: Are there adequate tests?
3. **Documentation**: Is it well documented?
4. **Style**: Does it follow coding standards?
5. **Performance**: Are there any performance concerns?
6. **Security**: Are there any security implications?
7. **Maintainability**: Is the code easy to understand and maintain?

## Additional Guidelines

### Security

- Never commit secrets or credentials
- Use environment variables for sensitive data
- Report security vulnerabilities via [SECURITY.md](SECURITY.md)

### Performance

- Consider performance implications
- Add benchmarks for performance-critical code
- Use profiling when optimizing

### Dependencies

- Minimize new dependencies
- Justify why new dependencies are needed
- Pin dependency versions in requirements.txt

### API Design

- Keep APIs simple and intuitive
- Maintain backwards compatibility when possible
- Document breaking changes clearly

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: See [SECURITY.md](SECURITY.md)
- **Chat**: Join our Discord/Slack (if available)

## Recognition

Contributors are recognized in:
- [CHANGELOG.md](CHANGELOG.md) for their contributions
- GitHub contributors page
- Release notes

Thank you for contributing to Kagami! 🎉

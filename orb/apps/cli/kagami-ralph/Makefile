.PHONY: install dev build test lint typecheck clean

# Install dependencies
install:
	npm install

# Development server
dev:
	npm run dev

# Production build
build:
	npm run build

# Run all tests
test:
	npm test

# Run tests in watch mode
test:watch:
	npm run test -- --watch

# Run E2E tests
test:e2e:
	npm run test:e2e

# Lint
lint:
	npm run lint

# Type check
typecheck:
	npm run typecheck

# Format code
format:
	npm run format

# Clean build artifacts
clean:
	rm -rf dist/ node_modules/ coverage/ playwright-report/ test-results/

# CI: Full validation
ci: install lint typecheck test build
	@echo "✅ All CI checks passed"

# Help
help:
	@echo "Kagami Ralph AI Monitor - Make targets:"
	@echo "  install    - Install dependencies"
	@echo "  dev        - Start development server"
	@echo "  build      - Production build"
	@echo "  test       - Run unit + integration tests"
	@echo "  test:e2e   - Run end-to-end tests"
	@echo "  lint       - Lint TypeScript code"
	@echo "  typecheck  - Run TypeScript compiler"
	@echo "  format     - Format code with Prettier"
	@echo "  clean      - Remove build artifacts"
	@echo "  ci         - Run all CI checks"

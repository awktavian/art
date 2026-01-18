# Dockerfile for Visual Regression Test Baseline Generation
#
# This creates a consistent Linux environment for generating visual test baselines.
# Using a standardized environment ensures snapshots match across different developer machines.
#
# Usage:
#   docker build -t kagami-visual-tests -f tests/visual/Dockerfile .
#   docker run --rm -v $(pwd)/tests/visual/__snapshots__:/app/tests/visual/__snapshots__ kagami-visual-tests
#
# Colony: Crystal (e7) - Verification & Polish

FROM mcr.microsoft.com/playwright:v1.48.0-jammy

# Set working directory
WORKDIR /app

# Set environment variables
ENV NODE_ENV=test
ENV CI=true
ENV DOCKER_BASELINE=true
# Disable GPU for consistent rendering
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Copy package files first for better caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Install Playwright browsers (all of them for comprehensive testing)
RUN npx playwright install --with-deps

# Copy application source
COPY . .

# Create snapshots directory
RUN mkdir -p tests/visual/__snapshots__

# Default command: update all snapshots
CMD ["npx", "playwright", "test", "--update-snapshots"]

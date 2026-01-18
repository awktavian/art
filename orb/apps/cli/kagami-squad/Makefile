# Kagami Squad — Build

VERSION := 0.1.0
BINARY := ks
GOFLAGS := -ldflags="-s -w -X main.version=$(VERSION)"
INSTALL_DIR := $(HOME)/.local/bin

.PHONY: all build install uninstall clean test fmt

all: build

build:
	@echo "Building $(BINARY)..."
	go build $(GOFLAGS) -o $(BINARY) .
	@echo "Done: ./$(BINARY)"

install: build
	@mkdir -p $(INSTALL_DIR)
	cp $(BINARY) $(INSTALL_DIR)/$(BINARY)
	@echo "Installed: $(INSTALL_DIR)/$(BINARY)"

uninstall:
	rm -f $(INSTALL_DIR)/$(BINARY)
	@echo "Uninstalled"

clean:
	rm -f $(BINARY)
	rm -rf build/

test:
	go test -v ./...

fmt:
	go fmt ./...

# Cross-platform builds
build-all: clean
	@mkdir -p build
	GOOS=darwin GOARCH=arm64 go build $(GOFLAGS) -o build/$(BINARY)-darwin-arm64 .
	GOOS=darwin GOARCH=amd64 go build $(GOFLAGS) -o build/$(BINARY)-darwin-amd64 .
	GOOS=linux GOARCH=amd64 go build $(GOFLAGS) -o build/$(BINARY)-linux-amd64 .
	GOOS=linux GOARCH=arm64 go build $(GOFLAGS) -o build/$(BINARY)-linux-arm64 .
	GOOS=windows GOARCH=amd64 go build $(GOFLAGS) -o build/$(BINARY)-windows-amd64.exe .
	@echo "Built all platforms in build/"

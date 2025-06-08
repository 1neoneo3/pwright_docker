.PHONY: build run dev debug clean help run-playwright playwright-dev test cloud-run-setup cloud-run-execute cloud-run-logs gcs-list build-nocache build-prod build-dev size-check gcp-build gcp-push

# Default target
.DEFAULT_GOAL := help

# Variables
APP_NAME = steam-scraper
DOCKER_COMPOSE = DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose
DOCKER_COMPOSE_DEV = DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose -f docker-compose.dev.yml
PROJECT_ID = capable-blend-244100
REGION = asia-northeast1
JOB_NAME = steam-scraper-job
BUCKET_NAME = $(PROJECT_ID)-scraper-results
BUILD_DATE = $(shell date +%Y%m%d)
DOCKER_TAG = $(APP_NAME):$(BUILD_DATE)
GCP_REGISTRY = asia-northeast1-docker.pkg.dev
GCP_REPO = $(PROJECT_ID)/steam-scraper
GCP_IMAGE = $(GCP_REGISTRY)/$(GCP_REPO)/$(APP_NAME)

# Targets
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker image with cache
	@echo "Building Docker image with cache..."
	$(DOCKER_COMPOSE) build --build-arg BUILDKIT_INLINE_CACHE=1

build-nocache: ## Build the Docker image without cache
	@echo "Building Docker image without cache..."
	$(DOCKER_COMPOSE) build --no-cache

build-prod: ## Build production Docker image with version tag
	@echo "Building production Docker image with tag $(DOCKER_TAG)..."
	DOCKER_BUILDKIT=1 docker build -t $(DOCKER_TAG) -t $(APP_NAME):latest --build-arg BUILDKIT_INLINE_CACHE=1 .

build-dev: ## Build development Docker image
	@echo "Building development Docker image..."
	$(DOCKER_COMPOSE_DEV) build --build-arg BUILDKIT_INLINE_CACHE=1

run: ## Run the application in production mode
	@echo "Running application in production mode..."
	$(DOCKER_COMPOSE) up

run-once: ## Run the application once and exit
	@echo "Running application once and exiting..."
	$(DOCKER_COMPOSE) run --rm app

run-playwright: ## Run the Playwright scraper in production mode
	@echo "Running Playwright scraper in production mode..."
	$(DOCKER_COMPOSE) up playwright

playwright-once: ## Run the Playwright scraper once and exit
	@echo "Running Playwright scraper once and exiting..."
	$(DOCKER_COMPOSE) run --rm playwright

dev: ## Run the application in development mode
	@echo "Running application in development mode..."
	$(DOCKER_COMPOSE_DEV) up

dev-build: ## Build and run the application in development mode
	@echo "Building and running application in development mode..."
	$(DOCKER_COMPOSE_DEV) up --build

playwright-dev: ## Run the Playwright scraper in development mode
	@echo "Running Playwright scraper in development mode with debugger on port 5679..."
	$(DOCKER_COMPOSE_DEV) up playwright

debug: ## Run the application with debugger attached
	@echo "Running application with debugger on port 5678..."
	$(DOCKER_COMPOSE_DEV) up app

logs: ## View application logs
	@echo "Viewing application logs..."
	$(DOCKER_COMPOSE) logs -f app

playwright-logs: ## View Playwright scraper logs
	@echo "Viewing Playwright scraper logs..."
	$(DOCKER_COMPOSE) logs -f playwright
	
test: ## Run a simple test script to verify the Docker setup
	@echo "Running simple test script..."
	docker run --rm -v $(PWD):/app python:3.12-slim python /app/scripts/main.py
	
benchmark-build: ## Measure Docker build time
	@echo "Measuring Docker build time..."
	@time DOCKER_BUILDKIT=1 docker build -t $(APP_NAME):benchmark .

size-check: ## Check the size of the built Docker image
	@echo "Checking Docker image size..."
	@docker images $(APP_NAME):latest --format "{{.Size}}"

stop: ## Stop running containers
	@echo "Stopping containers..."
	$(DOCKER_COMPOSE) stop

clean: ## Stop and remove containers, networks, and volumes
	@echo "Cleaning up Docker resources..."
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE_DEV) down -v
	@echo "Removing generated files..."
	rm -f steam_top_sellers.json

# Google Cloud Run Job コマンド
cloud-run-setup: ## Set up Google Cloud Run Job
	@echo "Setting up Google Cloud Run Job..."
	./scripts/cloud_run_setup.sh

cloud-run-execute: ## Execute the Cloud Run Job manually
	@echo "Executing Cloud Run Job..."
	gcloud run jobs execute $(JOB_NAME) --region=$(REGION) --project=$(PROJECT_ID)

cloud-run-logs: ## View Cloud Run Job logs
	@echo "Viewing Cloud Run Job logs..."
	gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$(JOB_NAME)" \
		--limit=20 \
		--format=json \
		--project=$(PROJECT_ID)

gcs-list: ## List data in Cloud Storage
	@echo "Listing data in Cloud Storage..."
	gsutil ls -l gs://$(BUCKET_NAME)/
	
gcp-build: ## Build Docker image for GCP Artifact Registry
	@echo "Building Docker image for GCP Artifact Registry..."
	docker buildx create --use
	docker buildx build --platform linux/amd64 --push -t $(GCP_IMAGE):$(BUILD_DATE) -t $(GCP_IMAGE):latest .

gcp-deploy: gcp-build ## Build and push Docker image to GCP Artifact Registry
	@echo "Docker image successfully built and pushed to GCP Artifact Registry"
	@echo "Image: $(GCP_IMAGE):latest"
	@echo "Tag: $(GCP_IMAGE):$(BUILD_DATE)"
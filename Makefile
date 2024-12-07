REGISTRY := localhost:5001
DOCKER_FLAGS := --load
ifdef PUSH
    DOCKER_FLAGS += --push
endif

build-dev:
	docker build . -f Dockerfile.dev --tag $(REGISTRY)/mods $(DOCKER_FLAGS)

build-fuse:
	docker build . -f Dockerfile.fuse --tag $(REGISTRY)/mods-fuse:latest $(DOCKER_FLAGS)

build-base:
	docker build . -f Dockerfile.base --tag $(REGISTRY)/mods-base:latest $(DOCKER_FLAGS)

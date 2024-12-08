REGISTRY := localhost:5001/mods
DOCKER_FLAGS := --load
ifdef PUSH
    DOCKER_FLAGS += --push
endif

build-dev:
	docker build . -f Dockerfile.dev --tag $(REGISTRY)/dev $(DOCKER_FLAGS)

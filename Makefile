build-dev:
	docker build . -f Dockerfile.dev --tag localhost:5001/mods --load

build-kind:
	docker build . -f Dockerfile.dev --tag localhost:5001/mods --push--load

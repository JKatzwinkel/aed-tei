
DEFAULT_GOAL := help

.PHONY: help vocabulary add-translations


help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z.\/_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dump: ## create BTS corpus dump folder
	mkdir dump

dump/vocabulary.zip: | dump
	wget https://edoc.bbaw.de/files/2919/vocabulary.zip -O dump/vocabulary.zip

vocabulary: dump/vocabulary.zip ## download BTS vocabulary ZIP dump

add-translations: dump/vocabulary.zip ## add translations from BTS dump to AED XML dictionary
	pipenv run python peret.py add-translations -i dump/vocabulary.zip

add-relations: dump/vocabulary.zip ## add relations from BTS dump to AED XML dictionary
	pipenv run python peret.py add-relations -i dump/vocabulary.zip

test: vocabulary ## run tests
	pipenv run pytest --doctest-modules peret.py

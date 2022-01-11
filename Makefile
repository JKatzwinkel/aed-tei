
DEFAULT_GOAL := help

.PHONY: help vocabulary corpus aed-dictionary add-translations add-relations test


help: ## print target description
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z.\/_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dump: ## create BTS corpus dump folder
	mkdir dump

dump/vocabulary.zip: | dump
	wget https://edoc.bbaw.de/files/2919/vocabulary.zip -O dump/vocabulary.zip

vocabulary: dump/vocabulary.zip ## download BTS vocabulary ZIP dump

dump/corpus.zip: | dump
	wget https://edoc.bbaw.de/files/2919/corpus.zip -O dump/corpus.zip

corpus: dump/corpus.zip ## download BTS corpus ZIP dump

dump/gh-pages.zip: | dump
	wget https://github.com/simondschweitzer/aed/archive/refs/heads/gh-pages.zip -O dump/gh-pages.zip

aed-dictionary: dump/gh-pages.zip ## download AED dictionary HTML files ZIP archive

add-translations: vocabulary ## add translations from BTS dump to AED XML dictionary
	pipenv run peret add-translations -i dump/vocabulary.zip

add-relations: vocabulary ## add relations from BTS dump to AED XML dictionary
	pipenv run peret add-relations -i dump/vocabulary.zip

add-ths-dateranges: vocabulary ## add date ranges from BTS dump to AED XML thesaurus
	pipenv run peret add-ths-dateranges -i dump/vocabulary.zip -f files/thesaurus.xml

validate-ths-dateranges: ## find thesaurus entries with invalid date ranges
	pipenv run shemu ths-dates > invalid-ths-dates.csv

test: ## run tests
	pipenv run pytest --doctest-modules peret

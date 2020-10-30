OUTPUT_DIR=public_html
DB_DIR=repositories
MAINTAINER_MAPPING=pagure_owner_alias.json

help:
	@echo "sync-repositories: download RPM repository metadata for active releases"
	@echo "fetch-maintainers: download package-maintainer mapping from dist-git"
	@echo "html: generate static website"
	@echo "js: generate js"
	@echo "setup-js: get js dependencies"
	@echo "all: all of the above, in order"
	@echo "clean: remove artefacts"

all: sync-repositories fetch-maintainers html js

html-only: sync-repositories fetch-maintainers html

sync-repositories:
	mkdir -p $(DB_DIR)
	bin/fetch-repository-dbs.py --target-dir $(DB_DIR)

fetch-maintainers:
	curl https://src.fedoraproject.org/extras/pagure_owner_alias.json -o $(MAINTAINER_MAPPING)

html:
	mkdir -p $(OUTPUT_DIR)/assets
	cp -r assets/* $(OUTPUT_DIR)/assets
	bin/generate-html.py --target-dir $(OUTPUT_DIR)

js:
	cd vue && npm run prod
	mkdir -p $(OUTPUT_DIR)/assets/js
	cp vue/dist/* $(OUTPUT_DIR)/assets/js

js-dev:
	cd vue && npm run build
	mkdir -p $(OUTPUT_DIR)/assets/js
	cp vue/dist/* $(OUTPUT_DIR)/assets/js

setup-js:
	cd vue && npm i

clean:
	rm -r $(OUTPUT_DIR) $(DB_DIR) $(MAINTAINER_MAPPING)

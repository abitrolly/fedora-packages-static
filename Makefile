OUTPUT_DIR?=public_html
DB_DIR?=repositories
MAINTAINER_MAPPING?=pagure_owner_alias.json
PRODUCT_VERSION_MAPPING?=product_version_mapping.json

help:
	@echo "sync-repositories: download RPM repository metadata for active releases"
	@echo "fetch-data: download package-maintainer mapping from dist-git and release version mapping from pdc"
	@echo "html: generate static website"
	@echo "js: generate js"
	@echo "setup-js: get js dependencies"
	@echo "all: all of the above, in order"
	@echo "clean: remove artefacts"
	@echo "update-solr: update solr index. must have SOLR_CORE and SOLR_URL defined"

ifneq (,$(wildcard vue/node_modules))
all: sync-repositories fetch-data html js
else
all: sync-repositories fetch-data html setup-js js
endif

html-only: sync-repositories fetch-data html

update-solr:
	bin/update-solr.py

sync-repositories:
	mkdir -p $(DB_DIR)
	bin/fetch-repository-dbs.py --target-dir $(DB_DIR)

fetch-data:
	curl https://src.fedoraproject.org/extras/pagure_owner_alias.json -o $(MAINTAINER_MAPPING)
	bin/get-product-names.py

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

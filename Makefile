OUTPUT_DIR=public_html
DB_DIR=repositories
MAINTAINER_MAPPING=pagure_owner_alias.json

help:
	@echo "sync-repositories: download RPM repository metadata for active releases"
	@echo "fetch-maintainers: download package-maintainer mapping from dist-git"
	@echo "html: generate static website"
	@echo "all: all of the above, in order"
	@echo "clean: remove artefacts"

all: sync-repositories fetch-maintainers html

sync-repositories:
	mkdir -p $(DB_DIR)
	bin/fetch-repository-dbs.py --target-dir $(DB_DIR)

fetch-maintainers:
	curl https://src.fedoraproject.org/extras/pagure_owner_alias.json -o $(MAINTAINER_MAPPING)

html:
	mkdir -p $(OUTPUT_DIR)
	bin/generate-html.py --target-dir $(OUTPUT_DIR)

clean:
	rm -r $(OUTPUT_DIR) $(DB_DIR) $(MAINTAINER_MAPPING)

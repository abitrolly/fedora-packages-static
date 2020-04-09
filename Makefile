OUTPUT_DIR=public_html
DB_DIR=repositories

all: html

sync-repositories:
	mkdir -p $(DB_DIR)
	bin/fetch-repository-dbs.py --target-dir $(DB_DIR)

fetch-maintainers:
	curl https://src.fedoraproject.org/extras/pagure_owner_alias.json -O pagure_owner_aliase.json

html:
	rm -fr $(OUTPUT_DIR)
	mkdir -p $(OUTPUT_DIR)
	bin/generate-html.py --target-dir $(OUTPUT_DIR)

clean:
	rm -r $(OUTPUT_DIR) $(DB_DIR)

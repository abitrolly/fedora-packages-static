# fedora-packages-static

This project replaces the former Fedora [packages
app](https://apps.fedoraproject.org/packages/) which is built atop now dead
librairies and a pain to maintain. See *[The packages app has a short
runway](https://lists.fedoraproject.org/archives/list/infrastructure@lists.fedoraproject.org/thread/WWQG4RE5PSR5I2GND5SVWGMZRJNVRRPS/)*
for context.

This project generates a static page for each package, which is then indexed by Solr.

With the exception of the MIT `assets/css/bootstrap.min.css`, the content of
this repository is licensed under the GPLv3.

## Dependencies

The scripts contained in this repository depend on:

* `make`
* `curl`
* `python3`
* `python3-requests`
* `python3-jinja2`
* `python3-defusedxml`

## Usage

* Download repository metadata for active releases: `make sync-repositories`
* Download package-maintainers mapping from dist-git: `make fetch-maintainers`
* Generate static website: `make html`
* Install npm dependencies: `make setup-js`

* All at once: `make all`
* Help message: `make help`
* Clean artefacts (generated and downloaded): `make clean`

## Running with Solr

To run fedora-packages-static with functioning search:

```bash
mkdir container_folder public_html
docker-compose up
```

Solr will be availible at http://localhost:8983/ and fedora-packages-static will be at http://localhost:8080/

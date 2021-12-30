# fedora-packages-static [![Azure CI Status](https://dev.azure.com/fedora-packages/Fedora%20Packages%20Static%20CI/_apis/build/status/Fedora%20Packages%20Static%20CI)](https://dev.azure.com/fedora-packages/Fedora%20Packages%20Static%20CI/_build?definitionId=1)

Links: [Production Website](https://packages.fedoraproject.org/),
[Staging Website](https://packages.stg.fedoraproject.org/)

This project replaces the former Fedora packages
app which was built atop now dead libraries and was a pain to maintain. See *[The packages app has a short
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
* `python3-tqdm`
* `python3-libdnf`

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
docker-compose build
docker-compose up
```

Solr will be available at http://localhost:8983/ and fedora-packages-static will be at http://localhost:8080/

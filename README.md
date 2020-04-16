# fedora-packages-static

This project intends to replace the current Fedora [packages
app](https://apps.fedoraproject.org/packages/) which is built atop now dead
librairies and a pain to maintain. See *[The packages app has a short
runway](https://lists.fedoraproject.org/archives/list/infrastructure@lists.fedoraproject.org/thread/WWQG4RE5PSR5I2GND5SVWGMZRJNVRRPS/)*
for context.

The idea here is to generate a static page for every package and index it using
an independent tool such as [Yacy](https://yacy.net/).

## TODO

* Clean code, make pylint happy.
* Define license (likely MIT, GLPv3 would be nice).
* Fix EPEL8 support.
* Display dependencies in package detail page.
* Build container for use in CommunityShift.
* Use pkgKey correct pkgKey to generate changelog/files.

## Dependencies

The scripts contained in this repository depend

* `make`
* `curl`
* `python3`
* `python3-requests`
* `python3-jinja2`

## Usage

* Download repository metadata for active releases: `make sync-repositories`
* Download package-maintainers mapping from dist-git: `make fetch-maintainers`
* Generate static website: `make html`

* All at once: `make all`
* Help message: `make help`
* Clean artefacts (generated and downloaded): `make clean`

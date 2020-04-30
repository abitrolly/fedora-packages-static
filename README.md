# fedora-packages-static

This project intends to replace the current Fedora [packages
app](https://apps.fedoraproject.org/packages/) which is built atop now dead
librairies and a pain to maintain. See *[The packages app has a short
runway](https://lists.fedoraproject.org/archives/list/infrastructure@lists.fedoraproject.org/thread/WWQG4RE5PSR5I2GND5SVWGMZRJNVRRPS/)*
for context.

The idea here is to generate a static page for every package and index it using
an independent tool such as [Yacy](https://yacy.net/).

With the exception of the MIT `assets/css/bootstrap.min.css`, the content of
this repository is licensed under the GPLv3.

## TODO

* Clean code, make pylint and humans happy.
* Display dependencies in package detail page.
* Add support for modular and flatpak repositories.
* Build container for use in CommunityShift.

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

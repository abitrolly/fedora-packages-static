#!/bin/sh

cd /usr/local/src/packages
make all
rsync -av --progress --delete public_html/ /srv/packages
rm -rf public_html

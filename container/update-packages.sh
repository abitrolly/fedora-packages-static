#!/bin/sh
OUTPUT_DIR=/tmp/packages/
cd /usr/local/src/packages
make all
rsync -av --progress --delete $OUTPUT_DIR /srv/packages
make update-solr
rm -rf $OUTPUT_DIR

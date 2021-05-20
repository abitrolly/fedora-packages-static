#!/bin/sh
cd /usr/local/src/packages
while true; do
    make html-only
    make update-solr
    sleep 3600
done

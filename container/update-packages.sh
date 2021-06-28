#!/bin/sh
cd /usr/local/src/packages
INIT_FILE=/etc/packages/.init_complete
if [[ ! -f "$INIT_FILE" ]]; then
  make all
  make update-solr
  touch $INIT_FILE
  sleep 3600
fi
while true; do
    make html-only
    make update-solr
    sleep 3600
done

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
    if [ ! -f /etc/packages/no_update ]; then
        make html-only
        make update-solr
    else
        echo "Update script paused by /etc/packages/no_update file."
    fi
    sleep 3600
done

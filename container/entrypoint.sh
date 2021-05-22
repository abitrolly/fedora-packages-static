#!/bin/sh
cd /etc/packages
rm -f nginx.pid supervisord.pid
INIT_FILE=.init_complete
if [[ ! -f "$INIT_FILE" ]]; then
  mkdir -p /var/run/supervisor
  make OUTPUT_DIR=/srv/packages all
  make update-solr
  touch $INIT_FILE
fi
echo "Starting web server..."
supervisord -c /etc/supervisord.conf

#!/bin/sh
cd /etc/packages
rm -f nginx.pid supervisord.pid
INIT_FILE=.init_complete
if [[ ! -f "$INIT_FILE" ]]; then
  mkdir -p /var/run/supervisor
fi
echo "Starting web server..."
supervisord -c /etc/supervisord.conf

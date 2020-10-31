#!/bin/sh

anacron -s
make OUTPUT_DIR=/srv/packages all
echo "Starting web server..."
nginx

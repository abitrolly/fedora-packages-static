#!/bin/sh

anacron -s
make html-only
nginx

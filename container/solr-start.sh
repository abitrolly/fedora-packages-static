#!/bin/bash
#
# Taken from https://github.com/docker-solr/docker-solr/blob/master/scripts/solr-precreate
# Chnaged so that Solr itself is called with -p 8983 (otherwise it will crash).
set -e

if [[ "${VERBOSE:-}" == "yes" ]]; then
    set -x
fi

# init script for handling an empty /var/solr
/opt/docker-solr/scripts/init-var-solr

. /opt/docker-solr/scripts/run-initdb

# Manually arrange config files into directory structure solr needs because openshift just won't let this be simple
mkdir -p /var/solr/openshift/packages
cp /opt/solr/server/solr/configsets/packages/schema.xml /var/solr/openshift/packages

mkdir -p /var/solr/openshift/packages/conf
cp /opt/solr/server/solr/configsets/packages/solrconfig.xml /var/solr/openshift/packages/conf

# Create the core
/opt/docker-solr/scripts/precreate-core "packages" /var/solr/openshift/packages

#!/bin/bash
#
# start solr in the foreground
set -e

if [[ "$VERBOSE" == "yes" ]]; then
    set -x
fi

EXTRA_ARGS=()
EXTRA_ARGS+=(-p 8983)

# Start of https://github.com/docker-solr/docker-solr/blob/master/scripts/solr-fg
if [[ -z "${OOM:-}" ]]; then
  OOM='none'
fi
case "$OOM" in
  'script')
    EXTRA_ARGS+=(-a '-XX:OnOutOfMemoryError=/opt/docker-solr/scripts/oom_solr.sh')
    ;;
  'exit')
    # recommended
    EXTRA_ARGS+=(-a '-XX:+ExitOnOutOfMemoryError')
    ;;
  'crash')
    EXTRA_ARGS+=(-a '-XX:+CrashOnOutOfMemoryError')
    ;;
  'none'|'')
    ;;
  *)
   echo "Unsupported value in OOM=$OOM"
   exit 1
esac

echo "Starting Solr $SOLR_VERSION"
# determine TINI default. If it is already set, assume the user knows what they want
if [[ -z "${TINI:-}" ]]; then
  if [[ "$$" == 1 ]]; then
    # Default to running tini, so we can run with an OOM script and have 'kill -9' work
    TINI=yes
  else
    # Presumably we're already running under tini through 'docker --init', in which case we
    # don't need to run it twice.
    # It's also possible that we're run from a wrapper script without exec,
    # in which case running tini would not be ideal either.
    TINI=no
  fi
fi
if [[ "$TINI" == yes ]]; then
  exec /usr/bin/tini -- solr -f "${EXTRA_ARGS[@]}"
elif [[ "$TINI" == no ]]; then
  exec solr -f "${EXTRA_ARGS[@]}"
else
  echo "invalid value TINI=$TINI"
  exit 1
fi

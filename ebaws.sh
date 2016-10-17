#!/usr/bin/env bash
#
# Auto-updater && self-invoker
#

set -e  # Work even if somebody does "sh thisscript.sh".

BASENAME=$(basename $0)
USAGE="Usage: $BASENAME [OPTIONS]
A self-updating wrapper script for the EBAWS. When run, updates
to both this script and EBAWS will be downloaded and installed.

Help for ebaws itself cannot be provided until it is installed.

  --debug                                   attempt experimental installation
  -h, --help                                print this help
  -n, --non-interactive,                    run without asking for user input
  --no-self-upgrade                         do not download updates
  --os-packages-only                        install OS dependencies and exit
  -v, --verbose                             provide more output

All arguments are accepted and forwarded to the EBAWS client when run."

for arg in "$@" ; do
  case "$arg" in
    --debug)
      DEBUG=1;;
    --os-packages-only)
      OS_PACKAGES_ONLY=1;;
    --no-self-upgrade)
      # Do not upgrade this script (also prevents client upgrades, because each
      # copy of the script pins a hash of the python client)
      NO_SELF_UPGRADE=1;;
    --help)
      HELP=1;;
    --non-interactive)
      ASSUME_YES=1;;
    --verbose)
      VERBOSE=1;;
    -[!-]*)
      while getopts ":hnv" short_arg $arg; do
        case "$short_arg" in
          h)
            HELP=1;;
          n)
            ASSUME_YES=1;;
          v)
            VERBOSE=1;;
        esac
      done;;
  esac
done

# Upgrade step
if [ "$NO_SELF_UPGRADE" != 1 ]; then
    echo "Checking for updates..."
    set +e
    PIP_OUT=`pip install --no-cache-dir --upgrade ebaws.py 2>&1`
    PIP_STATUS=$?
    set -e

    # Report error. (Otherwise, be quiet.)
    if [ "$PIP_STATUS" != 0 ]; then
      echo "Had a problem while installing Python packages:"
      echo "$PIP_OUT"
      echo ""
      echo "Running the previous version"
    fi
fi

# Invoke the python client directly
/usr/local/bin/ebaws "$@"


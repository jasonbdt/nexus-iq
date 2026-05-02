#!/bin/sh
set -e
mkdir -p /usr/src/ddragon/cdn
if [ "${SKIP_DDRAGON_CHOWN:-0}" != "1" ]; then
    chown -R app:app /usr/src/ddragon
fi
exec su-exec app "$@"

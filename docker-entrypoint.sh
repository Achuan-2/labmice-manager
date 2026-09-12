#!/bin/sh
set -eu

APP_UID=10001
APP_GID=10001

if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data /app/excel

    # Bind mounts keep the permissions from the NAS. Fix them before dropping
    # privileges so a newly selected host directory works on first startup.
    chown -R "$APP_UID:$APP_GID" /app/data
    chmod -R u+rwX /app/data
    chmod -R a+rX /app/excel

    exec gosu "$APP_UID:$APP_GID" "$@"
fi

exec "$@"

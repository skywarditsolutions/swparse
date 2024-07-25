#!/bin/bash
export MODE="dev"
source .env.dev
if [ ! -d "./data/" ]; then mkdir -p ./data/; fi
if [ ! -d "./data/$MINIO_BUCKET" ]; then mkdir -p ./data/$MINIO_BUCKET; fi
docker compose --env-file ".env.dev" -f docker-compose.dev.yaml up --build --remove-orphans &
mc='docker exec -it minio-client mc'
MODE="dev" litestar --app-dir ./src/swparse workers run --debug &
MODE="dev" litestar --app-dir ./src/swparse run --debug &
# $mc admin user add minio/ $MINIO_CONSOLE_USER $MINIO_CONSOLE_PASSWORD
# $mc admin policy add minio/ consoleAdmin /root/.mc/admin.json
# $mc admin policy set minio consoleAdmin user=$MINIO_CONSOLE_USER
sleep infinity
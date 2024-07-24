#!/bin/bash
source .env
if [ ! -d "./data/" ]; then mkdir -p ./data/; fi
if [ ! -d "./data/$MINIO_BUCKET" ]; then mkdir -p ./data/$MINIO_BUCKET; fi
docker-compose pull
docker-compose up --remove-orphans -d
mc='docker exec -it minio-client mc'
litestar --app-dir ./src/swparse  workers run &
litestar --app-dir ./src/swparse  run &
# create console user and policy

# $mc admin user add minio/ $MINIO_CONSOLE_USER $MINIO_CONSOLE_PASSWORD
# $mc admin policy add minio/ consoleAdmin /root/.mc/admin.json
# $mc admin policy set minio consoleAdmin user=$MINIO_CONSOLE_USER


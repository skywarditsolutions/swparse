#!/bin/bash
export MODE="prod"
cp .env.example .env
source .env
if [ ! -d "./data/" ]; then mkdir -p ./data/; fi
if [ ! -d "./data/$MINIO_BUCKET" ]; then mkdir -p ./data/$MINIO_BUCKET; fi
docker compose -f docker-compose.prod.yaml up --build --remove-orphans -d
docker system prune -f
mc='docker exec -it minio-client mc'
# $mc admin user add minio/ $MINIO_CONSOLE_USER $MINIO_CONSOLE_PASSWORD
# $mc admin policy add minio/ consoleAdmin /root/.mc/admin.json
# $mc admin policy set minio consoleAdmin user=$MINIO_CONSOLE_USER

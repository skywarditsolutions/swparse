# pdm install
docker compose -f docker-compose.infra.yml up -d
swparse run -d &
swparse workers run -d &
sleep infinity
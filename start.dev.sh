# pdm install
docker compose -f docker-compose.infra.yml up --build -d
swparse workers run -d &
sleep 4
swparse run -d &
sleep infinity
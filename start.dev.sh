# pdm install
docker compose -f docker-compose.infra.yml up --build &
.venv/bin/swparse workers run -d &
sleep 4
.venv/bin/swparse run -d &
sleep infinity

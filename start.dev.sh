# pdm install
docker compose -f docker-compose.infra.yml down

docker compose -f docker-compose.infra.yml up --build 
# .venv/bin/swparse workers run &
# sleep 4
.venv/bin/swparse run -d 
# sleep infinity

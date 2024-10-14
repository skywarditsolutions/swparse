pdm install
docker compose -f docker-compose.cpu.yml -f docker-compose.override.yml up
swparse run -d
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up --build -d
docker volume prune
docker system prune -f
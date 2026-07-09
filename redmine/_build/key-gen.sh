echo "POSTGRES_USER=redmine" >> .env
echo "POSTGRES_DB=redmine" >> .env
echo "POSTGRES_PASSWORD=$(openssl rand -base64 48 | tr -d '\n')" >> .env
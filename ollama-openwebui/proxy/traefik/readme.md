```
# modify configs, generate ssl certs and place in "certs" directory
docker|podman build -t traefik .
docker|podman run --rm -it --name traefik -p 80:80 -p 443:443 -p 8080:8080 traefik:latest
```
## SELinux policies for running containers via Udica

https://www.redhat.com/en/blog/generate-selinux-policies-containers-with-udica

```sh
# Create a sonarqube user with home directory first (don't run container as root)

#create directories for container

mkdir -p /home/sonarqube/{data,extensions,logs,temp}

#enfore SELinux

setenforce 1
sed -e "s#SELINUX=.*#SELINUX=enforcing#" -i /etc/selinux/config

#install udica

dnf install -y udica

#build and run sonarqube container

podman network create sonarnet

podman build -t sonarqube .

podman run --rm -it \
    -v /home/sonarqube/data:/opt/sonarqube/data:rw -v /home/sonarqube/extensions:/opt/sonarqube/extensions:rw \
    -v /home/sonarqube/logs:/opt/sonarqube/logs:ro -v /home/sonarqube/temp:/opt/sonarqube/temp:rw \
    --network sonarnet -p 9000:9000 --name sonarqube -d sonarqube

#generate policy

podman inspect sonarqube > sonarqube.json
udica -j sonarqube.json sonarqube

#use policy

semodule -i sonarqube.cil /usr/share/udica/templates/{base_container.cil,net_container.cil,home_container.cil}

#Restart the container with: "--security-opt label=type:sonarqube.process" parameter

podman run --security-opt label=type:sonarqube.process \
  -v /home/sonarqube/data:/opt/sonarqube/data:rw -v /home/sonarqube/extensions:/opt/sonarqube/extensions:rw \
  -v /home/sonarqube/logs:/opt/sonarqube/logs:ro -v /home/sonarqube/temp:/opt/sonarqube/temp:rw \
  --network sonarnet -p 9000:9000 --rm -it sonarqube -d sonarqube

```

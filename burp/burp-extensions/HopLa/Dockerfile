FROM docker.io/gradle:9.6.1-jdk21
WORKDIR /data
COPY src .
COPY build.gradle .
COPY settings.gradle .
CMD "gradle build --debug --warning-mode all"
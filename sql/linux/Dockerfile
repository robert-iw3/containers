FROM mcr.microsoft.com/mssql/server:2025-latest

# Install tools if needed (sqlcmd is included)
USER root
RUN apt-get update && apt-get install -y gnupg2 curl
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y mssql-tools18 unixodbc-dev
ENV PATH=$PATH:/opt/mssql-tools18/bin
USER mssql

# Copy startup script
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

ENTRYPOINT ["/startup.sh"]
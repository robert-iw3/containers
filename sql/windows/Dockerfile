FROM mcr.microsoft.com/windows/server:ltsc2025

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# Copy the SQL Server installer (download and place in build context)
COPY SQLServer2025-x64-ENU.exe C:/setup.exe

# Install SQL Server Developer edition silently with temporary SA password
RUN Start-Process -Wait -FilePath C:/setup.exe -ArgumentList @( \
    '/Q', \
    '/ACTION=Install', \
    '/IACCEPTSQLSERVERLICENSETERMS', \
    '/FEATURES=SQLEngine,Tools', \
    '/INSTANCENAME=MSSQLSERVER', \
    '/SQLSVCACCOUNT=NT Authority\\System', \
    '/SQLSVCSTARTUPTYPE=Automatic', \
    '/SQLSYSADMINACCOUNTS=BUILTIN\\Administrators', \
    '/AGTSVCACCOUNT=NT Authority\\System', \
    '/AGTSVCSTARTUPTYPE=Automatic', \
    '/TCPENABLED=1', \
    '/NPENABLED=1', \
    '/SECURITYMODE=SQL', \
    '/SAPWD=TempP@ssw0rd!', \
    '/PID=Developer' \
)

# Copy startup script
COPY startup.ps1 C:/startup.ps1

# Expose SQL Server port
EXPOSE 1433

# Set startup script as entrypoint
CMD ["powershell", "-File", "C:/startup.ps1"]
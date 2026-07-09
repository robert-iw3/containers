@ECHO OFF
set SplunkApp=TA-Applocker

powershell.exe -executionPolicy RemoteSigned -command ". '%SPLUNK_HOME%\etc\apps\%SplunkApp%\bin\%1'"

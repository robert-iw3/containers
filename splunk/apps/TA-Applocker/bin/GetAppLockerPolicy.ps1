$ErrorActionPreference="SilentlyContinue"

# Get AppLocker Policy
Try{
    Get-AppLockerPolicy -Local -xml
}
Catch{
    $time = [Math]::Floor([decimal](Get-Date(Get-Date).ToUniversalTime()-uformat "%s"))
$error_msg = "<time>" + $time +  "</time><ApplockerError>Failed To Run AppLocker Policy Output</ApplockerError>"
write-output $error_msg
}

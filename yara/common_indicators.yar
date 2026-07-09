// sudo yara -q -s -r -w -n ./common_indicators.yar <dir or file> > yara_common_indicators.log
rule Suspicious_Base64_Payload {
    meta:
        description = "Detects suspicious base64 encoded payloads"
        severity = "high"
    strings:
        $b64_long = /[A-Za-z0-9+\/]{100,}={0,2}/ fullword ascii
        $eval = "eval" ascii
        $exec = "exec" ascii
        $decode = "base64" ascii
    condition:
        $b64_long and ($eval or $exec or $decode)
}

rule Reverse_Shell_Patterns {
    meta:
        description = "Detects reverse shell command patterns"
        severity = "critical"
    strings:
        $nc_bind = "/nc.*-l.*-p.*[0-9]+/" ascii
        $nc_connect = /nc.*[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+.*[0-9]+/ ascii
        $bash_tcp = "/dev/tcp/" ascii
        $python_socket = "socket.socket(socket.AF_INET" ascii
        $perl_socket = "IO::Socket::INET" ascii
        $socat_reverse = "/socat.*tcp.*exec/" ascii
        $mknod_backpipe = "/mknod.*backpipe.*p/" ascii
    condition:
        any of them
}

rule Webshell_Indicators {
    meta:
        description = "Detects common webshell patterns"
        severity = "high"
    strings:
        $php_eval = /eval\s*\(\s*\$_(GET|POST|REQUEST)/ ascii
        $php_system = /system\s*\(\s*\$_(GET|POST|REQUEST)/ ascii
        $php_passthru = /passthru\s*\(\s*\$_(GET|POST|REQUEST)/ ascii
        $php_shell_exec = /shell_exec\s*\(\s*\$_(GET|POST|REQUEST)/ ascii
        $asp_eval = "eval(Request" ascii
        $jsp_runtime = "Runtime.getRuntime().exec" ascii
        $generic_backdoor = /\$_(GET|POST)\[.*\]\s*=.*exec/ ascii
    condition:
        any of them
}

rule Crypto_Miner_Indicators {
    meta:
        description = "Detects cryptocurrency mining malware"
        severity = "high"
    strings:
        $stratum1 = "stratum+tcp://" ascii
        $stratum2 = "stratum+ssl://" ascii
        $xmrig = "xmrig" ascii
        $cpuminer = "cpuminer" ascii
        $pool1 = "pool.supportxmr.com" ascii
        $pool2 = "xmr-usa-east1.nanopool.org" ascii
        $wallet = "/[49][A-Za-z0-9]{94}/" ascii
        $mining_algo = "/cryptonight|scrypt|sha256|x11/" ascii
    condition:
        any of them
}

rule Process_Injection_Techniques {
    meta:
        description = "Detects process injection indicators"
        severity = "medium"
    strings:
        $ptrace = "ptrace" ascii
        $proc_mem = "/proc/*/mem" ascii
        $ld_preload = "LD_PRELOAD" ascii
        $dlopen = "dlopen" ascii
        $mmap_exec = "PROT_EXEC" ascii
        $shellcode = { 31 c0 50 68 }
    condition:
        any of them
}

rule Persistence_Mechanisms {
    meta:
        description = "Detects persistence establishment attempts"
        severity = "medium"
    strings:
        $crontab = "crontab -e" ascii
        $systemd_service = ".service" ascii
        $bashrc = ".bashrc" ascii
        $profile = ".profile" ascii
        $ssh_keys = "authorized_keys" ascii
        $startup = "/etc/init.d/" ascii
        $rc_declare = "/etc/rc.local" ascii
    condition:
        any of them
}

rule APT_Lateral_Movement {
    meta:
        description = "Detects APT lateral movement tools"
        severity = "critical"
    strings:
        $psexec = "psexec" ascii
        $wmic = "wmic process call create" ascii
        $schtasks = "schtasks /create" ascii
        $powershell_encoded = "powershell -enc" ascii
        $mimikatz = "sekurlsa::logonpasswords" ascii
        $bloodhound = "SharpHound" ascii
        $cobalt_strike = "beacon" ascii
    condition:
        any of them
}

rule Data_Exfiltration {
    meta:
        description = "Detects data exfiltration attempts"
        severity = "high"
    strings:
        $curl_upload = "/curl.*-T.*http/" ascii
        $wget_post = "/wget.*--post-file/" ascii
        $nc_file = /nc.*<.*\/.*\// ascii
        $base64_pipe = /base64.*\|.*curl/ ascii
        $tar_remote = /tar.*\|.*nc/ ascii
        $scp_remote = /scp.*@/ ascii
    condition:
        any of them
}
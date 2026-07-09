## yara-scanner: Simple IOC and YARA scanner for Linux

## Dependencies

#### Python modules

[colorama](https://pypi.org/project/colorama/)
| [progressbar2](https://pypi.org/project/progressbar2/)
| [psutil](https://pypi.org/project/psutil/)
| [requests](https://pypi.org/project/requests/)
| [yara-python](https://pypi.org/project/yara-python/)

#### Base YARA rules

[Neo23x0/signature-base](https://github.com/Neo23x0/signature-base)
| [reversinglabs-yara-rules](https://github.com/reversinglabs/reversinglabs-yara-rules)

#### Custom YARA rules

[elastic/protections-artifacts](https://github.com/elastic/protections-artifacts)
| [PhishingKit-Yara-Rules](https://github.com/t4d/PhishingKit-Yara-Rules)
| [malpedia/signator-rules](https://github.com/malpedia/signator-rules)
| [YARAHQ/yara-forge](https://github.com/YARAHQ/yara-forge)

#### Alpine Linux

```
apk add bash gcc git linux-headers musl-dev openssl-dev python3 python3-dev py3-pip
```

#### Arch Linux

```
pacman -S bash gcc git python3 python-devtools python-pip
```

#### Debian / Ubuntu / Linux Mint / Kali Linux

```
apt -y install gcc git libssl-dev python3 python3-dev python3-venv
update-alternatives --install /usr/bin/python python /usr/bin/python3 1
```

#### Rocky Linux / AlmaLinux

```
dnf -y install bash gcc git openssl-devel python3 python3-devel python3-pip
```

#### Void Linux

```
xbps-install -Sy bash gcc git openssl-devel python3 python3-devel
```

## Installation

#### Manual

```
git clone https://github.com/c0m4r/yara-scanner.git
cd yara-scanner
./deploy.sh
./yara-scanner.py --nolog --intense -p ./test
```

## Daemonized usage

#### Server

Start as a daemon and bind on the default localhost:1337

```
./yara-scanner.py -d -s 20000 --noindicator --csv --nolog --intense
```

You can also change default bind address/port with `--listen-host`
and `--listen-port` args. Check `--help` for details.

Check example [init files](/addons/etc) for OpenRC and systemd integration.

#### Client

```
./client.py -p /path/to/scan
```

As of now, the server accepts a plain path and an optional space-separated auth key.

```
echo "./test" | nc localhost 1337 ; echo
echo "./test authkey" | nc localhost 1337 ; echo
```

Possible responses:

| Answer                               | Level   | Score  |
| ------------------------------------ | ------- | ------ |
| RESULT: Indicators detected!         | ALERT   | >= 100 |
| RESULT: Suspicious objects detected! | WARNING | >= 60  |
| RESULT: SYSTEM SEEMS TO BE CLEAN.    | NOTICE  | >= 40  |

In `--auth` mode it will respond with `authorization required` if authkey was not sent or `unauthorized` if authkey is invalid.

## New features

* Rewritten for Linux
* A single file scan if a given path is a file
* Daemon mode `-d` with listening socket `--listen-host 127.0.0.1` `--listen-port 1337`
  accepting scans requested from client.py
  * PID file `yara-scanner.pid` is created in the program directory if running in daemon mode,
    you change its path with `--pidfile /path/to/pidfile`
  * Optional auth key `--auth somethingRandomHere` in daemon mode
    (just a dumb string authorization, can be intercepted and read from the process list)
* You can disable one or more yara files, f.e. `--disable-yara-files apt_vpnfilter.yar,yara_mixed_ext_vars.yar`
* Exclude files by hash as proposed by [rafaelarcanjo](https://github.com/rafaelarcanjo)
  in [Neo23x0/Loki/pull/204](https://github.com/Neo23x0/Loki/pull/204). See: [excludes.cfg](/config/excludes.cfg)
* Initial implementation of process scanning under Linux (scan_processes_linux()):
  * File Name Checks: works with signature-base/iocs/filename-iocs.txt (note: linux iocs missing by default)
  * Process connections: for now, it only shows detected connections per process
  * Process Masquerading Detection: reports non-empty /proc/PID/maps of processes that uses square brackets in their cmdlines
* Progress bar (experimental) can be enabled with --progress
* Force yara-scanner to follow symlinks (be aware: may lead to RAM overflow) with --followlinks
* Custom yara rules sources
  * Some additional YARA rule sources have been added and you can also choose your own
  * Custom yara ruleset dir can be set with --custom signature-custom/yara/name
  * To avoid conflicts between rules, it's recommended to use only one source at a time

## Usage

Run a program with --help to view usage information.

See: [Usage](https://github.com/c0m4r/yara-scanner/wiki/Usage)

## Custom signatures

Apart from the signature-base there are some example
custom signature rulesets being pulled by the upgrader script.

Custom signatures can be used independently as a supplement,
but you should avoid mixing the rule sources, as this may lead to conflicts between rules.

Use `--custom` to point the scanner to a different directory where the rules are stored.
It will process all the .yar and .yara stored in that directory; don't point to a file, as this won't work.

Example usage of the custom ruleset:

```
./yara-scanner.py --intense --progress -p ./sample/webshell/ --custom signature-custom/yara/protections-artifacts-main/
```

These additional custom YARA rules has been proven to work* with yara-scanner:

* [SupportIntelligence/Icewater](https://github.com/SupportIntelligence/Icewater)
* [intezer/yara-rules](https://github.com/intezer/yara-rules)
* [jeFF0Falltrades/YARA-Signatures](https://github.com/jeFF0Falltrades/YARA-Signatures)
* [evthehermit/YaraRules](https://github.com/kevthehermit/YaraRules)
* [MalGamy/YARA_Rules](https://github.com/MalGamy/YARA_Rules)
* [advanced-threat-research/Yara-Rules](https://github.com/advanced-threat-research/Yara-Rules)
* [securitymagic/yara](https://github.com/securitymagic/yara)
* [telekom-security/malware_analysis](https://github.com/telekom-security/malware_analysis)
* [tenable/yara-rules](https://github.com/tenable/yara-rules)

\* That doesn't mean they will actually detect something; just that they are processed properly by the yara-python


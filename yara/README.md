## Yara

https://virustotal.github.io/yara/

csv export:

https://github.com/Neo23x0/yarAnalyzer

```sh
# yara classic
podman build -t yara .
# yara-x
podman build -f yara-x.Dockerfile -t yara-x

podman network create yara

podman run --rm -it --security-opt=no-new-privileges -v <file to be analyzed or directory>:/malware --network yara --name yara -d yara

podman exec yara yara include_rules.yar -rg /malware

podman exec yara yara "path/to/rule1.yar" "path/to/rule2.yar" "path/to/rule3.yar" -rg /malware

#scanning local images/containers

podman run --rm -it --security-opt=no-new-privileges -v /home/<the username>/.local/share/containers/storage:/malware --network yara --name yara -d yara
podman run --rm -it --security-opt=no-new-privileges -v /var/lib/containers/storage:/malware --network yara --name yara -d yara

podman exec yara yara include_rules.yar -rg /malware
```

make a include_rules.yar

```sh
#example
include "/rules/APT/APT_APT15.yar"
include "/rules/APT/APT_APT17.yar"
include "/rules/APT/APT_APT29_Grizzly_Steppe.yar"
include "/rules/APT/APT_APT3102.yar"
include "/rules/APT/APT_APT9002.yar"
```

tip in vim, get rid of all \n

:g/^$/d

vscode

find:
^(.+)$

replace:
include "/rules/$1"

## yara - find files matching patterns and rules written in a special-purpose language.

manpage:

SYNOPSIS

yara [OPTION]... [NAMESPACE:]RULES_FILE... FILE | DIR | PID

DESCRIPTION

yara scans the given FILE, all files contained in directory DIR, or the process identified by PID looking for matches of patterns and rules provided in a special purpose-language. The rules are read from one or more RULES_FILE.

The options to yara(1) are:

```yaml
--atom-quality-table
Path to a file with the atom quality table.

-C --compiled-rules
RULES_FILE contains rules already compiled with yarac.

-c --count
Print number of matches only.

-d --define=identifier=value
Define an external variable. This option can be used multiple times.

--fail-on-warnings
Treat warnings as errors. Has no effect if used with --no-warnings.

-f --fast-scan
Speeds up scanning by searching only for the first occurrence of each pattern.

-i identifier --identifier=identifier
Print rules named identifier and ignore the rest. This option can be used multiple times.

--max-process-memory-chunk=size
While scanning process memory read data in chunks of the given size in bytes.

-l number --max-rules=number
Abort scanning after a number of rules matched.

--max-strings-per-rule=number
Set maximum number of strings per rule (default=10000)

-x --module-data=module=file
Pass file's content as extra data to module. This option can be used multiple times.

-n --negate
Print rules that doesn't apply (negate).

-w --no-warnings
Disable warnings.

-m --print-meta
Print metadata associated to the rule.

-D --print-module-data
Print module data.

-e --print-namespace
Print namespace associated to the rule.

-S --print-stats
Print rules' statistics.

-s --print-strings
Print strings found in the file.

-L --print-string-length
Print length of strings found in the file.

-g --print-tags
Print the tags associated to the rule.

-r --recursive
Scan files in directories recursively. It follows symlinks.

--scan-list
Scan files listed in FILE, one per line.

-z size --skip-larger=size
Skip files larger than the given size in bytes when scanning a directory.

-k slots --stack-size=slots
Set maximum stack size to the specified number of slots.

-t tag --tag=tag
Print rules tagged as tag and ignore the rest. This option can be used multiple times.

-p number --threads=number
Use the specified number of threads to scan a directory.

-a seconds --timeout=seconds
Abort scanning after a number of seconds has elapsed.

-v --version
Show version information.

```

EXAMPLES

```sh
$ yara /foo/bar/rules .
```
Apply rules on /foo/bar/rules to all files on current directory. Subdirectories are not scanned.
```sh
$ yara -t Packer -t Compiler /foo/bar/rules bazfile
```
Apply rules on /foo/bar/rules to bazfile. Only reports rules tagged as Packer or Compiler.
```sh
$ cat /foo/bar/rules | yara -r /foo
```
Scan all files in the /foo directory and its subdirectories. Rules are read from standard input.
```sh
$ yara -d mybool=true -d myint=5 -d mystring="my string" /foo/bar/rules bazfile
```
Defines three external variables mybool myint and mystring.
```sh
$ yara -x cuckoo=cuckoo_json_report /foo/bar/rules bazfile
```
Apply rules on /foo/bar/rules to bazfile while passing the content of cuckoo_json_report to the cuckoo module.

#!/usr/bin/env bash
# Assess a Splunk instance against the applicable SRG requirements.
#
# READ-ONLY AND AUTH-FREE. Every observation comes from `splunk btool <conf> list
# --debug`, which needs no credentials, no cached session and no running splunkd,
# and which reports the file each setting came from. Nothing here writes to the
# instance, so this can run on a production system without a change request.
#
# WHAT IT REPORTS, AND WHAT IT DOES NOT. It records what the instance is
# configured to do and which file supplied each value. It does not decide whether
# a value satisfies a requirement: that needs a per-requirement criterion, which
# is a separate input. Until one exists a requirement's status is not_reviewed,
# which is the honest status and the one a checklist exists to surface.
#
# THE FILE THAT WON IS THE POINT. A setting present in an app can be outranked by
# $SPLUNK_HOME/etc/system/local, which beats every app. Reporting a value without
# naming its source would let the tool claim a setting was applied when something
# else supplied it. That is the failure this column exists to prevent.
#
#   assess.sh                          assess the local instance
#   assess.sh (containers: use bin/in-container.sh)
#   assess.sh --out DIR                where results are written
#   assess.sh --sign-with KEY          sign the chain-of-custody manifest
#
# EXIT CONTRACT
#   0 every check row was observed
#   1 one or more rows could not be observed (a conf btool would not read)
#   2 nothing could be observed; the instance did not answer
#   3 this script could not run
set -uo pipefail

OUT=""; SPLUNK_HOME_OVERRIDE=""; CHECKS=""; SIGN_WITH=""
HERE="$(cd "$(dirname "$0")/.." && pwd)"

# Splunk discovery and the privilege guard are shared: the guard is safety-critical
# and a guard copied into five scripts is one that drifts. Sourced BEFORE the option
# loop so its defaults are set and the options then override them.
# The shared library sits at ../lib when this module is staged flat (as
# in-container.sh stages it) and at ../../lib in the repository layout. Search
# rather than assume: a wrong guess fails at the first line of every run.
LIB=""
for _c in "$(dirname "$0")/../lib" "$(dirname "$0")/../../lib" "$(dirname "$0")"; do
    [ -r "${_c}/lib-target.sh" ] && { LIB="$(cd "$_c" && pwd)/lib-target.sh"; break; }
done
[ -n "$LIB" ] || { printf 'cannot find lib-target.sh near %s\n' "$(dirname "$0")" >&2; exit 3; }
. "$LIB"

# Kept verbatim so the privilege guard can print the command to re-run.
TGT_ORIGINAL_ARGS="$*"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --out)         OUT="${2:-}"; shift 2 ;;
        --checks)      CHECKS="${2:-}"; shift 2 ;;
        --sign-with)   SIGN_WITH="${2:-}"; shift 2 ;;
        --splunk-home) SPLUNK_HOME_OVERRIDE="${2:-}"; shift 2 ;;
        --allow-wrong-user) TGT_ALLOW_WRONG_USER=1; shift ;;
        -h|--help)     sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown argument: %s\n' "$1" >&2; exit 3 ;;
    esac
done

[ -n "$CHECKS" ] || CHECKS="${HERE}/inventory/checks.tsv"
[ -r "$CHECKS" ] || { printf 'no check data at %s\n' "$CHECKS" >&2
                      printf 'run assess/bin/parse-mechanisms.py first\n' >&2; exit 3; }
TGT_SPLUNK_HOME_HINT="$SPLUNK_HOME_OVERRIDE"
target_init || exit 3

[ -n "$OUT" ] || OUT="${HERE}/out"
mkdir -p "$OUT" 2>/dev/null || { printf 'cannot write to %s\n' "$OUT" >&2; exit 3; }

if [ -t 1 ]; then G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; Z=$'\033[0m'
else G=""; R=""; Y=""; B=""; Z=""; fi




# The Splunk image ships without `hostname`, the same way it ships without curl,
# so the name is read from the places that do not need a binary.
LABEL="$(hostname 2>/dev/null)"
[ -n "$LABEL" ] || LABEL="${HOSTNAME:-}"
[ -n "$LABEL" ] || LABEL="$(cat /etc/hostname 2>/dev/null | sed -n 1p)"
[ -n "$LABEL" ] || LABEL="local"
LABEL="$(printf '%s' "$LABEL" | tr -c 'A-Za-z0-9._-' '_')"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RESULTS="${OUT}/assessment-${LABEL}-${STAMP}.tsv"

# THE RAW btool OUTPUT IS THE PRIMARY EVIDENCE AND IS RETAINED.
#
# An earlier version of this script collected it into a temporary directory and
# deleted it on exit, keeping only the parsed table. That makes every finding
# unverifiable: a reader cannot re-derive it, and cannot tell whether the table
# was edited after the fact. The raw output is kept, digested, and the digest
# recorded in the manifest, so anyone can recompute the findings from the evidence
# and detect alteration of either.
EVID="${OUT}/evidence-${LABEL}-${STAMP}"
MANIFEST="${EVID}/MANIFEST.txt"
mkdir -p "$EVID" || { printf 'cannot create %s\n' "$EVID" >&2; exit 3; }
WORK="$EVID"

# sha256sum where present, openssl otherwise: a Splunk host carries at least one.
digest() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 "$1" | awk '{print $NF}'
    else printf 'unavailable'; fi
}

printf '%s== Assessing %s%s\n' "$B" "$LABEL" "$Z"
printf '   SPLUNK_HOME %s\n' "$SPLUNK_HOME"
printf '   checks      %s\n' "$CHECKS"

ver="$(sh_in "'$SP' version" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' | sed -n 1p)"
printf '   version     %s\n' "${ver:-unknown}"

# ------------------------------------------------------------ 1. read each conf
# btool is invoked ONCE PER CONF FILE, not once per check row. There are over a
# thousand rows and a few dozen files, and a per-row invocation would spend the
# run on process startup.
confs="$(awk -F'\t' 'NR>1 && $3!="" {print $3}' "$CHECKS" | sort -u)"
nconf=0; nfail=0
printf '\n%s== Reading configuration%s\n' "$B" "$Z"
for c in $confs; do
    stem="${c%.conf}"
    raw="${WORK}/${stem}.raw"
    sh_in "'$SP' btool ${stem} list --debug" > "$raw" 2>/dev/null
    if [ ! -s "$raw" ]; then
        printf '  %s[ ?? ]%s %-24s btool returned nothing\n' "$Y" "$Z" "$c"
        nfail=$((nfail+1))
        : > "${WORK}/${stem}.map"
        continue
    fi
    # Flatten to: stanza \t key \t value \t source_file
    # A --debug line is "<source-file> <content>"; content is either "[stanza]" or
    # "key = value". The stanza carries forward until the next one.
    # Field 5 is the btool line verbatim, so a finding can quote what was read
    # rather than a reconstruction of it. Tabs are the field separator here, so a
    # tab inside a value becomes a space; nothing else is altered.
    # SECRETS ARE REDACTED HERE, before anything derived from them is written.
    #
    # A checklist is shared: attached to a package, mailed, handed to an assessor.
    # The TLS private key passphrase sits in server.conf as a $7$ value that is
    # recoverable with splunk.secret, so publishing it in a finding would disclose
    # the key. The KEY NAME and its SOURCE FILE are the assessable facts and are
    # kept; only the value is withheld, with its length and a short digest so two
    # runs can still be compared without exposing it.
    #
    # Matched two ways: a named key, and a value shaped like an encrypted secret.
    # Matching the substring "password" would wrongly redact minPasswordLength and
    # the rest of the password POLICY, which an assessor must be able to read.
    awk '
        function redact(k, v,   d, i, c) {
            if (k ~ /^(sslPassword|sslKeysfilePassword|pass4SymmKey|bindDNpassword|privKeyPassword|sslRootCAPathPassword)$/ ||
                v ~ /^\$[0-9]\$/ || v ~ /^AQ[A-Za-z0-9+\/=]{20,}$/)
                return "<redacted: " length(v) " chars>"
            return v
        }
        { line=$0; gsub(/\t/," ",line); file=$1; $1=""; sub(/^[ \t]+/,"") }
        /^\[/ { stanza=$0; gsub(/^\[|\]$/,"",stanza); next }
        /=/   { eq=index($0,"=");
                k=substr($0,1,eq-1); v=substr($0,eq+1);
                gsub(/^[ \t]+|[ \t]+$/,"",k); gsub(/^[ \t]+|[ \t]+$/,"",v);
                r=redact(k,v);
                if (r != v) { line = file "  " k " = " r }
                if (k!="") printf "%s\t%s\t%s\t%s\t%s\n", stanza, k, r, file, line }
    ' "$raw" > "${WORK}/${stem}.map"
    rows="$(wc -l < "${WORK}/${stem}.map")"
    printf '%s\t%s\t%s\t%s\n' "$c" "$SP btool ${stem} list --debug" \
        "$(digest "$raw")" "$(wc -c < "$raw")" >> "${EVID}/.digests"
    printf '  %s[ OK ]%s %-24s %s setting(s)\n' "$G" "$Z" "$c" "$rows"
    nconf=$((nconf+1))
done

# ---------------------------------------------------- 1b. instance facts
# NOT EVERY REQUIREMENT IS ABOUT A CONFIGURATION SETTING.
#
# "must be a version supported by the vendor" is assessable - the instance states
# its version plainly - but it is not a setting, and a check vocabulary that can
# only name conf/stanza/key cannot express it. Assessors then recorded such
# requirements as impossible to decide, which conflates "cannot be configured"
# with "cannot be assessed". They are different: an assessment reads state.
#
# These facts are emitted as rows in the same shape as a setting, under the
# pseudo-configuration "fact", so a criterion can test them with the same
# operators: fact [instance] version matches ...
printf '\n%s== Instance facts%s\n' "$B" "$Z"
FACTS="${WORK}/fact.map"
: > "$FACTS"
put_fact() {
    [ -n "${2:-}" ] || return 0
    printf 'instance\t%s\t%s\tinstance state\t%s = %s\n' "$1" "$2" "$1" "$2" >> "$FACTS"
    printf '  %-26s %s\n' "$1" "$2"
}
ver_full="$(sh_in "'$SP' version" | sed -n 1p)"
put_fact version       "$(printf '%s' "$ver_full" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' | sed -n 1p)"
put_fact version_full  "$ver_full"
put_fact build         "$(printf '%s' "$ver_full" | sed -n 's/.*build \([0-9a-f]*\).*/\1/p')"
put_fact splunk_home   "$SPLUNK_HOME"
put_fact etc_owner     "$(sh_in "ls -ld '${SPLUNK_HOME}/etc' | awk '{print \$3}'")"
put_fact running_as    "$(id -un 2>/dev/null)"
put_fact splunkd_state "$(sh_in "'$SP' status" | grep -c 'splunkd is running' | sed 's/^0$/stopped/;s/^[1-9].*/running/')"
put_fact cluster_mode  "$(sh_in "'$SP' btool server list clustering --debug" | sed -n 's/.*[ ]mode = //p' | sed -n 1p)"
put_fact auth_type     "$(sh_in "'$SP' btool authentication list --debug" | sed -n 's/.*[ ]authType = //p' | sed -n 1p)"
put_fact local_accounts "$(sh_in "grep -c ':' '${SPLUNK_HOME}/etc/passwd'")"
put_fact btool_errors  "$(sh_in "'$SP' btool check" | grep -c 'Invalid key')"
put_fact config_files  "$(ls -1 "${WORK}"/*.map 2>/dev/null | wc -l)"
printf '%s\t%s\t%s\t%s\n' "fact" "$SP version; btool; id; ls" "$(digest "$FACTS")" "$(wc -c < "$FACTS")" >> "${EVID}/.digests"

# -------------------------------------------------------------- 2. join and emit
printf '\n%s== Observing each check row%s\n' "$B" "$Z"
{
  printf 'srg_id\tseverity\tconf\tstanza\tkey\tkey_status\tfound\tvalue\tsource\tprecedence\tobserved_line\n'
  awk -F'\t' -v work="$WORK" -v home="$SPLUNK_HOME" '
    function classify(f) {
        # Which layer supplied the winning value. system/local outranks every app,
        # so a value from there cannot be overridden by the hardening app.
        if (f ~ /\/etc\/system\/local\//)   return "system_local"
        if (f ~ /\/etc\/system\/default\//) return "system_default"
        if (f ~ /\/etc\/apps\//)            return "app"
        if (f ~ /\/etc\/users\//)           return "user"
        return "other"
    }
    # A benchmark names a family of settings with a placeholder: [role_<roleName>],
    # [tcpout:<group>], SEDCMD-<class>. Looked up literally such a name matches
    # nothing, so the row was recorded absent while the instance carried 26 real
    # role stanzas. Expand the placeholder against the stanzas and keys btool
    # actually reported, and emit one observation per real match, so the results
    # carry what is there rather than the absence of a name that cannot exist.
    #
    # The separator before a placeholder is optional along with it, because Splunk
    # inherits: a value in [tcpout] is the default for every [tcpout:group]. A
    # placeholder also matches the empty name, which is how btool reports a
    # setting made once for every stanza of a kind.
    function to_regex(pat,   out, i, c, inph, sep) {
        out = "^"; inph = 0; sep = ""
        for (i = 1; i <= length(pat); i++) {
            c = substr(pat, i, 1)
            if (c == "<") {
                inph = 1
                if (sep != "") out = substr(out, 1, length(out) - length(sep)) "(" sep ".*)?"
                else           out = out ".*"
                sep = ""
                continue
            }
            if (c == ">") { inph = 0; continue }
            if (inph) continue
            if (index(".*+?[](){}|^$\\/-", c) > 0) { out = out "\\" c; sep = "\\" c }
            else                                    { out = out c;        sep = c }
            if (c != ":" && c != "-" && c != "_" && c != "/") sep = ""
        }
        return out "$"
    }

    NR==1 { next }
    {
        srg=$1; sev=$2; conf=$3; stanza=$4; key=$5; kst=$6
        stem=conf; sub(/\.conf$/,"",stem)
        map=work "/" stem ".map"
        if ((getline probe < map) < 0) {
            printf "%s\t%s\t%s\t%s\t%s\t%s\tunreadable\t\t\t\t\n", srg,sev,conf,stanza,key,kst
            next
        }
        close(map)

        wild = (stanza ~ /</ || key ~ /</)
        sre = (stanza ~ /</) ? to_regex(stanza) : ""
        kre = (key ~ /</)    ? tolower(to_regex(key)) : ""

        found="absent"; val=""; src=""; prec=""; lit=""
        n=0; hits=0
        while ((getline line < map) > 0) {
            split(line, F, "\t")
            if (sre != "") { if (F[1] !~ sre) continue }
            else if (stanza != "" && F[1] != stanza) continue
            if (key != "") {
                if (kre != "") { if (tolower(F[2]) !~ kre) continue }
                else if (tolower(F[2]) != tolower(key)) continue
                if (wild) {
                    # One row per real setting the placeholder names. The stanza
                    # and key recorded are the real ones, so the evidence quotes
                    # what exists; the criterion that asked is still identified
                    # by srg_id.
                    hits++
                    printf "%s\t%s\t%s\t%s\t%s\t%s\tpresent\t%s\t%s\t%s\t%s\n",
                           srg,sev,conf,F[1],F[2],kst,F[3],F[4],classify(F[4]),F[5]
                    continue
                }
                found="present"; val=F[3]; src=F[4]; prec=classify(F[4]); lit=F[5]; break
            } else {
                n++
                if (src == "") { src=F[4]; prec=classify(F[4]); lit=F[5] }
            }
        }
        close(map)

        if (wild && key != "") {
            # Nothing matched. Record the absence against the name as written, so
            # the row is still accounted for and the reason is visible.
            if (hits == 0)
                printf "%s\t%s\t%s\t%s\t%s\t%s\tabsent\t\t\t\t\n",
                       srg,sev,conf,stanza,key,kst
            next
        }
        if (key == "") { found = (n>0 ? "stanza_present" : "stanza_absent"); val=n }
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", srg,sev,conf,stanza,key,kst,found,val,src,prec,lit
    }
  ' "$CHECKS"
  # The facts are emitted as result rows under a reserved identifier, so a reader
  # of the results sees them without needing the evidence bundle. They are not a
  # requirement, which is why the identifier cannot collide with one.
  if [ -s "$FACTS" ]; then
      while IFS="	" read -r st key val src line; do
          printf '__instance__\t-\tfact\t%s\t%s\t-\tpresent\t%s\t%s\t%s\t%s\n' \
              "$st" "$key" "$val" "$src" "instance" "$line"
      done < "$FACTS"
  fi
} > "$RESULTS"

# ------------------------------------------------------- 3. chain of custody
# WHAT THIS DOES AND DOES NOT ESTABLISH.
#
# It records who collected the evidence, on what, by which command, when, and a
# SHA-256 over every artifact. That makes the evidence ATTRIBUTABLE, REPRODUCIBLE
# and TAMPER-EVIDENT: a reader can rerun the commands, recompute the findings from
# the retained output, and detect alteration of either.
#
# It is NOT non-repudiation. A digest computed by the same process that collected
# the evidence proves nothing against whoever controls that process. Repudiation
# is foreclosed only by a signature over the manifest using a key the collector
# does not hold, which is why --sign-with exists and why its absence is stated in
# the manifest rather than left for a reader to infer.
{
  printf 'Splunk configuration assessment - chain of custody\n'
  printf '=================================================\n\n'
  printf 'collected_utc       %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'collected_by        %s (uid %s)\n' "$(id -un 2>/dev/null || echo unknown)" "$(id -u 2>/dev/null || echo unknown)"
  printf 'host                %s\n' "$LABEL"
  printf 'kernel              %s\n' "$(uname -srm 2>/dev/null || echo unknown)"
  printf 'splunk_home         %s\n' "$SPLUNK_HOME"
  printf 'splunk_version      %s\n' "$(sh_in "'$SP' version" | sed -n 1p)"
  printf 'tool                %s\n' "$0"
  printf 'check_data          %s\n' "$CHECKS"
  printf 'check_data_sha256   %s\n' "$(digest "$CHECKS")"
  printf 'results             %s\n' "$(basename "$RESULTS")"
  printf 'results_sha256      %s\n' "$(digest "$RESULTS")"
  printf '\nREAD OPERATIONS ONLY. Every observation came from splunk btool, which reads\n'
  printf 'configuration and writes none. No value on this instance was changed.\n'
  printf '\nHANDLING. Values of credential-bearing settings are REDACTED from the results\n'
  printf 'and from anything generated from them, so a checklist can be shared. The raw\n'
  printf 'output below is unredacted by design, because a finding must be re-derivable\n'
  printf 'from it; protect this directory at the system\x27s own level.\n'
  printf '\nPRIMARY EVIDENCE - the raw output each finding derives from.\n'
  printf 'Recompute a digest with: sha256sum <file>\n\n'
  printf '%-26s %-64s %10s  %s\n' "CONF" "SHA256" "BYTES" "COMMAND"
  if [ -r "${EVID}/.digests" ]; then
      while IFS=$'\t' read -r c cmd dg sz; do
          printf '%-26s %-64s %10s  %s\n' "$c" "$dg" "$sz" "$cmd"
      done < "${EVID}/.digests"
  fi
  printf '\nSIGNATURE\n'
  if [ -n "$SIGN_WITH" ]; then printf 'manifest signed with %s; verify the .sig beside this file\n' "$SIGN_WITH"
  else printf 'unsigned. This manifest is tamper-evident, not non-repudiable: no key\n'
       printf 'outside the collecting process attests to it. Supply --sign-with KEY to\n'
       printf 'sign it with a key this process does not generate.\n'
  fi
} > "$MANIFEST"

# The manifest digests everything else, so its own digest is the single value a
# reader needs to carry forward. Recorded separately because a digest cannot
# cover the file it is written into.
MANIFEST_SHA="$(digest "$MANIFEST")"
printf '%s  %s\n' "$MANIFEST_SHA" "$(basename "$MANIFEST")" > "${MANIFEST}.sha256"

if [ -n "$SIGN_WITH" ]; then
    if [ ! -r "$SIGN_WITH" ]; then
        printf '  %ssigning key not readable: %s%s\n' "$Y" "$SIGN_WITH" "$Z" >&2
    elif openssl dgst -sha256 -sign "$SIGN_WITH" -out "${MANIFEST}.sig" "$MANIFEST" 2>/dev/null; then
        printf '  %s[ OK ]%s manifest signed            %s\n' "$G" "$Z" "$(basename "${MANIFEST}.sig")"
    else
        printf '  %scould not sign the manifest with %s%s\n' "$Y" "$SIGN_WITH" "$Z" >&2
    fi
fi

# --------------------------------------------------------------- 3. the verdict
tot="$(awk 'NR>1' "$RESULTS" | wc -l)"
obs="$(awk -F'\t' 'NR>1 && $7!="unreadable"' "$RESULTS" | wc -l)"
pres="$(awk -F'\t' 'NR>1 && $7=="present"' "$RESULTS" | wc -l)"
abs="$(awk -F'\t' 'NR>1 && $7=="absent"' "$RESULTS" | wc -l)"
unread="$(awk -F'\t' 'NR>1 && $7=="unreadable"' "$RESULTS" | wc -l)"
syslocal="$(awk -F'\t' 'NR>1 && $10=="system_local"' "$RESULTS" | wc -l)"
fromapp="$(awk -F'\t' 'NR>1 && $10=="app"' "$RESULTS" | wc -l)"
sysdef="$(awk -F'\t' 'NR>1 && $10=="system_default"' "$RESULTS" | wc -l)"
reqs="$(awk -F'\t' 'NR>1 {print $1}' "$RESULTS" | sort -u | wc -l)"

printf '  rows observed            %s of %s\n' "$obs" "$tot"
printf '  key present              %s\n' "$pres"
printf '  key absent               %s\n' "$abs"
[ "$unread" -gt 0 ] && printf '  %sunreadable               %s%s\n' "$Y" "$unread" "$Z"

printf '\n%s== Which layer supplied the winning value%s\n' "$B" "$Z"
printf '  system/local (outranks every app)   %s\n' "$syslocal"
printf '  an app                              %s\n' "$fromapp"
printf '  system/default (shipped)            %s\n' "$sysdef"

printf '\n%s== %s requirement(s) assessed, %s check row(s)%s\n' "$B" "$reqs" "$tot" "$Z"
printf '   results  : %s\n' "$RESULTS"
printf '   evidence : %s\n' "$EVID"
printf '   manifest : %s\n' "$MANIFEST"
printf '   sha256   : %s\n' "$MANIFEST_SHA"
printf '   Status per requirement is not_reviewed until a criterion exists for it;\n'
printf '   this run records the observed state and the file that supplied it.\n'

if   [ "$obs" -eq 0 ];     then printf '   %sNOTHING OBSERVED%s\n' "$R" "$Z"; exit 2
elif [ "$unread" -gt 0 ];  then printf '   %sINCOMPLETE%s\n' "$Y" "$Z"; exit 1
else printf '   %sCOMPLETE%s\n' "$G" "$Z"; exit 0; fi

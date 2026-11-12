#!/usr/bin/env bash
# Decide each requirement's status from an assessment and the rule files.
#
# SEPARATE FROM COLLECTION ON PURPOSE. assess.sh reads the instance; this reads
# what assess.sh wrote. So a criterion can be corrected and every past assessment
# re-decided without going near a Splunk instance again - which matters, because
# criteria change and instances should not be disturbed to re-ask a question
# already answered.
#
# It needs no Splunk, no credentials and no network. It is pure text over two
# inputs.
#
#   evaluate.sh --results FILE [--rules DIR] [--out DIR]
#
# EXIT CONTRACT
#   0  every requirement decided or honestly deferred
#   1  one or more requirements are Open
#   2  nothing could be decided
#   3  could not run
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS=""; RULES=""; OUT=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --results) RESULTS="${2:-}"; shift 2 ;;
        --rules)   RULES="${2:-}"; shift 2 ;;
        --out)     OUT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown argument: %s\n' "$1" >&2; exit 3 ;;
    esac
done
[ -n "$RULES" ]   || RULES="${HERE}/rules"
[ -r "$RESULTS" ] || { printf 'need --results from assess.sh\n' >&2; exit 3; }
[ -d "$RULES" ]   || { printf 'no rule files at %s\n' "$RULES" >&2; exit 3; }
[ -n "$OUT" ]     || OUT="$(dirname "$RESULTS")"

if [ -t 1 ]; then G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[1m'; Z=$'\033[0m'
else G=""; R=""; Y=""; B=""; Z=""; fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VERDICTS="${OUT}/verdicts-${STAMP}.tsv"

printf '%s== Deciding %s requirement(s)%s\n' "$B" "$(ls -1 "$RULES"/*.rule 2>/dev/null | wc -l)" "$Z"
printf '   results %s\n' "$(basename "$RESULTS")"
printf '   rules   %s\n\n' "$RULES"

# One awk pass. The observations are loaded first, then each rule file is read and
# its conditions tested against them.
awk -v G="$G" -v R="$R" -v Y="$Y" -v Z="$Z" '
    function norm(s) { gsub(/^[ \t]+|[ \t]+$/,"",s); return s }

    # ---- condition operators -------------------------------------------------
    # Each returns 1 pass, 0 fail. "Observed" means the key was found in the
    # merged configuration; absent is a legitimate observation, not a failure to
    # observe.
    function test_cond(op, want, got, found,   i, n, parts, lo) {
        if (op == "present")    return (found == "present")
        if (op == "absent")     return (found != "present")
        # The shipped Splunk configuration declares many settings with no value:
        # etc/system/default/alert_actions.conf carries "filename =" so the key
        # exists while nothing is configured. "absent" is false there, which
        # reports a finding against a feature that is switched off. "empty" is
        # the honest test for not-configured: the key is missing, or it is
        # declared and carries no value.
        if (op == "empty")      return (found != "present" || got == "")
        if (found != "present") return 0      # every other operator needs a value
        if (op == "non_empty")  return (got != "")
        if (op == "equals")     return (tolower(got) == tolower(want))
        if (op == "not_equals") return (tolower(got) != tolower(want))
        if (op == "not_matches") {
            if (want ~ /\(\?[=!<]/) return -1
            return !(got ~ want)
        }
        if (op == "matches") {
            # A pattern using a lookahead or lookbehind is PCRE, which this
            # evaluator cannot compile - and an uncompilable pattern aborts the
            # whole run, not just its own condition. Detected and deferred so one
            # bad criterion cannot take the evaluation down with it.
            if (want ~ /\(\?[=!<]/) return -1
            return (got ~ want)
        }
        if (op == "min")        return (got + 0 >= want + 0)
        if (op == "max")        return (got + 0 <= want + 0)
        if (op == "in" || op == "not_in") {
            n = split(want, parts, "|"); lo = 0
            for (i = 1; i <= n; i++) if (tolower(got) == tolower(norm(parts[i]))) lo = 1
            return (op == "in") ? lo : !lo
        }
        return -1                              # unknown operator: cannot decide
    }

    # ---- load the observations ----------------------------------------------
    FNR == 1 && FILENAME == RESULTS_FILE { next }
    FILENAME == RESULTS_FILE {
        split($0, f, "\t")
        k = f[3] "|" f[4] "|" tolower(f[5])
        FOUND[k] = f[7]; VAL[k] = f[8]; SRC[k] = f[9]; LAYER[k] = f[10]
        # A second index without the stanza, so a criterion written against a
        # placeholder stanza can be resolved against whatever stanzas exist.
        w = f[3] "|" tolower(f[5])
        WN[w]++
        WSTANZA[w, WN[w]] = f[4]; WFOUND[w, WN[w]] = f[7]; WVAL[w, WN[w]] = f[8]
        # A third index holding every row of the conf file, so a criterion whose
        # KEY is a placeholder - SEDCMD-<class> names a family of real settings -
        # can be matched against the keys the instance actually has.
        AN[f[3]]++
        AST[f[3], AN[f[3]]] = f[4];          AKEY[f[3], AN[f[3]]] = tolower(f[5])
        AFOUND[f[3], AN[f[3]]] = f[7];       AVAL[f[3], AN[f[3]]] = f[8]
        next
    }

    # A benchmark writes a family of settings as a placeholder: SEDCMD-<class>,
    # [tcpout:<group>]. Turn that into an anchored regex, with the literal parts
    # escaped so a dot in a setting name is not treated as "any character".
    #
    # A placeholder matches the EMPTY string as well, and the separator directly
    # before it becomes optional with it, for two reasons that are really one.
    # btool reports a setting made once for every stanza of a kind against the
    # default stanza, which has no name - so [<stanza name>] has to match "".
    # And Splunk inherits: a value in [tcpout] supplies the default for every
    # [tcpout:group], so a criterion on [tcpout:<group>] is satisfied by [tcpout].
    # Requiring a named stanza would report a finding against configuration that
    # does govern the listener.
    function to_regex(pat,   out, i, c, inph, sep) {
        out = "^"; inph = 0; sep = ""
        for (i = 1; i <= length(pat); i++) {
            c = substr(pat, i, 1)
            if (c == "<") {
                inph = 1
                if (sep != "") { out = substr(out, 1, length(out) - length(sep)) \
                                       "(" sep ".*)?" }
                else           { out = out ".*" }
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

    # Resolve a condition where the stanza, the key, or both are placeholders.
    # Existence tests pass if ANY real setting matching the pattern satisfies
    # them; value tests must hold for EVERY one, because a single stanza left at
    # a weak value is the exposure the requirement is about.
    function pattern(conf, stanza, key, op, want,   n, j, any, all, seen, r, sre, kre) {
        sre = to_regex(stanza); kre = to_regex(tolower(key))
        n = AN[conf]; any = 0; all = 1; seen = 0
        for (j = 1; j <= n; j++) {
            if (AST[conf, j] !~ sre) continue
            if (AKEY[conf, j] !~ kre) continue
            if (AFOUND[conf, j] != "present") continue
            seen++
            r = test_cond(op, want, AVAL[conf, j], AFOUND[conf, j])
            if (r == -1) return -1
            if (r) any = 1; else all = 0
        }
        if (seen == 0) return (op == "absent") ? 1 : 0
        if (op == "absent") return 0
        if (op == "present" || op == "non_empty") return any
        return all
    }

    # Resolve a condition whose stanza is a placeholder against real stanzas.
    function wildcard(conf, key, op, want,   w, j, n, any, all, r, seen) {
        w = conf "|" tolower(key)
        n = WN[w]
        if (n == 0) return (op == "absent") ? 1 : 0
        any = 0; all = 1; seen = 0
        for (j = 1; j <= n; j++) {
            if (WFOUND[w, j] != "present") continue
            seen++
            r = test_cond(op, want, WVAL[w, j], WFOUND[w, j])
            if (r == -1) return -1
            if (r) any = 1; else all = 0
        }
        if (seen == 0) return (op == "absent") ? 1 : 0
        if (op == "present" || op == "non_empty" || op == "absent") return any
        return all
    }

    # ---- read a rule file ----------------------------------------------------
    FNR == 1 {
        if (id != "") decide()
        id=""; sev=""; dec=""; ver=""; det=""; nck=0; fail=""; undec=""; conf_level=""
    }
    /^id:/            { id = norm(substr($0, index($0,":")+1)) }
    /^severity:/      { sev = norm(substr($0, index($0,":")+1)) }
    /^decidable:/     { dec = norm(substr($0, index($0,":")+1)) }
    /^confidence:/    { conf_level = norm(substr($0, index($0,":")+1)) }
    /^verified:/      { ver = norm(substr($0, index($0,":")+1)) }
    /^determination:/ { det = norm(substr($0, index($0,":")+1)) }
    /^check:/ {
        line = norm(substr($0, index($0,":")+1))
        # conf [stanza] key operator [value...]
        if (match(line, /\[[^]]*\]/)) {
            conf  = norm(substr(line, 1, RSTART-1))
            stanza = substr(line, RSTART+1, RLENGTH-2)
            rest  = norm(substr(line, RSTART+RLENGTH))
            n = split(rest, p, /[ \t]+/)
            key = p[1]; op = (n>=2 ? p[2] : "present"); val = ""
            for (i=3; i<=n; i++) val = (val=="" ? p[i] : val " " p[i])
            nck++
            CK_CONF[nck]=conf; CK_ST[nck]=stanza; CK_KEY[nck]=key
            CK_OP[nck]=op; CK_VAL[nck]=val
        }
    }
    END { if (id != "") decide() }

    function decide(   i, k, res, st, why, nf) {
        # inherent: the product satisfies the requirement by construction and no
        # setting can weaken it. That is a determination, not a deferral - the
        # evidence is the specification showing nothing exists to get wrong.
        #
        # NO RULE FILE SETS IT. Every requirement is machine or manual, so this
        # branch decides nothing today. Using it requires evidence that the
        # specification set defines no setting able to weaken the requirement,
        # which is a determination in its own right and is not made here; without
        # that evidence the honest value is manual.
        if (dec == "inherent") { st="not_a_finding"; why="satisfied by the product; no setting can weaken it" }
        else if (dec != "machine") { st="not_reviewed"; why="criterion cannot be decided from configuration" }
        else if (nck == 0)     { st="not_reviewed"; why="no conditions defined" }
        else {
            nf = 0
            for (i = 1; i <= nck; i++) {
                # A stanza written with angle brackets is the specification\x27s
                # notation for "any stanza of this kind" - [role_<roleName>],
                # [<index name>]. Matched literally it can never exist, so such a
                # condition could never pass on any instance: an unsatisfiable
                # criterion, not a strict one. 179 conditions were written this way.
                #
                # Resolved against the stanzas that actually exist: an existence
                # test passes if ANY stanza has the key; a value test must hold for
                # EVERY stanza that has it, which is the strict reading and the one
                # a requirement like "each index must enable integrity control"
                # means.
                # A placeholder in the KEY is the same notation applied to a
                # family of settings rather than a family of stanzas: props.conf
                # SEDCMD-<class> means every key named SEDCMD-something, and in a
                # roleMap_ stanza the keys are the role names themselves. Those
                # resolve against the keys the instance has, on the same any/every
                # reading used for stanzas.
                if (CK_KEY[i] ~ /</ || CK_ST[i] ~ /</) {
                    res = pattern(CK_CONF[i], CK_ST[i], CK_KEY[i], CK_OP[i], CK_VAL[i])
                } else {
                    k = CK_CONF[i] "|" CK_ST[i] "|" tolower(CK_KEY[i])
                    res = test_cond(CK_OP[i], CK_VAL[i], VAL[k], FOUND[k])
                }
                if (res == -1) {
                    if (CK_KEY[i] !~ /</)
                        undec = undec (undec==""?"":"; ") CK_KEY[i] " " CK_OP[i] \
                                ": criterion uses a construct this evaluator cannot apply"
                }
                else if (res == 0) {
                    nf++
                    fail = fail (fail==""?"":"; ") CK_CONF[i] " [" CK_ST[i] "] " CK_KEY[i] \
                           " " CK_OP[i] (CK_VAL[i]!="" ? " " CK_VAL[i] : "") \
                           " -> " (FOUND[k]=="present" ? "is " VAL[k] : "not set")
                }
            }
            if (undec != "")   { st="not_reviewed"; why=undec }
            else if (nf == 0)  { st="not_a_finding"; why="every condition met" }
            else               { st="open"; why=fail }
        }
        # CONFIDENCE DESCRIBES EVIDENCE, NOT REVIEW EFFORT.
        #
        # It previously read "verified" when a second assessor had re-read the same
        # benchmark text and specification files. That catches internal
        # inconsistency and nothing else: it cannot catch a specification that
        # disagrees with the product, which is where every real defect here has
        # been found. Calling it verification overstated it, so the levels now name
        # what was actually done.
        #
        #   derived     from the benchmark check text and the shipped specification
        #   documented  confirmed against the vendor published documentation
        #   tested      confirmed by observing the product behave that way
        conf = (conf_level != "") ? conf_level : "derived"
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n", id, sev, det, dec, st, conf, why
    }
' RESULTS_FILE="$RESULTS" "$RESULTS" "$RULES"/*.rule \
  | sort > "${VERDICTS}.body"

{ printf 'srg_id\tseverity\tdetermination\tdecidable\tstatus\tconfidence\treason\n'
  cat "${VERDICTS}.body"; } > "$VERDICTS"
rm -f "${VERDICTS}.body"

na="$(awk -F'\t' 'NR>1 && $5=="not_a_finding"' "$VERDICTS" | wc -l)"
c_der="$(awk -F'\t' 'NR>1 && $6=="derived"' "$VERDICTS" | wc -l)"
c_doc="$(awk -F'\t' 'NR>1 && $6=="documented"' "$VERDICTS" | wc -l)"
c_tst="$(awk -F'\t' 'NR>1 && $6=="tested"' "$VERDICTS" | wc -l)"
op="$(awk -F'\t' 'NR>1 && $5=="open"' "$VERDICTS" | wc -l)"
nr="$(awk -F'\t' 'NR>1 && $5=="not_reviewed"' "$VERDICTS" | wc -l)"
tot="$(awk 'NR>1' "$VERDICTS" | wc -l)"

printf '  %s[ NAF ]%s not a finding   %s\n' "$G" "$Z" "$na"
printf '  %s[OPEN ]%s open            %s\n' "$R" "$Z" "$op"
printf '  %s[  -  ]%s not reviewed    %s\n' "$Y" "$Z" "$nr"

printf '\n%s== why anything was deferred%s\n' "$B" "$Z"
awk -F'\t' 'NR>1 && $5=="not_reviewed" {print $7}' "$VERDICTS" \
  | sed 's/;.*//' | sort | uniq -c | sort -rn | head -5 \
  | awk '{n=$1; $1=""; printf "  %4d  %s\n", n, substr($0,2)}'

printf '\n%s== what each status rests on%s\n' "$B" "$Z"
printf '  derived from the benchmark and the shipped specification  %s\n' "$c_der"
printf '  confirmed against vendor documentation                    %s\n' "$c_doc"
printf '  confirmed by observing the product                        %s\n' "$c_tst"

printf '\n%s== %s requirement(s) decided%s\n' "$B" "$tot" "$Z"
printf '   verdicts: %s\n' "$VERDICTS"

if   [ "$tot" -eq 0 ]; then exit 2
elif [ "$op" -gt 0 ];  then exit 1
else exit 0; fi

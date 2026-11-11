#!/usr/bin/env bash
# What can this account actually do and see?
#
# An account that cannot search an index returns no results from it, which
# looks exactly like an index holding no data. Before concluding anything
# about the data, it is worth knowing which indexes you are allowed to see
# and which of them you are searching by default.
#
# It reports:
#
#   whether the credentials work at all
#   the roles the account holds, and the capabilities that follow
#   every index the account may search, and which are searched by default
#   whether the capabilities these maintenance scripts need are present
#
#   ./bin/check-credentials.sh --container splunk
#   ./bin/check-credentials.sh --container splunk --auth-file ~/.splunk-auth
set -uo pipefail
. "$(cd "$(dirname "$0")/../lib" && pwd)/common.sh"

usage() { sed -n '2,19p' "$0"; exit "${1:-0}"; }
im_parse_common "$@"
set -- "${IM_REST[@]:-}"
while [ $# -gt 0 ]; do
    case "${1:-}" in
        -h|--help) usage 0 ;;
        "") shift ;;
        *) im_die "unknown argument: $1" ;;
    esac
done
im_resolve_user
im_require_auth
WHO="${IM_AUTH%%:*}"

im_head "Do the credentials work"
if im_auth_works; then
    im_say "yes, as '$WHO'"
else
    im_warn "no. splunkd rejected them."
    im_warn "A rejected login and an empty index look the same in a search"
    im_warn "result, so fix this before reading anything else."
    exit 1
fi

# --- roles and capabilities --------------------------------------------
im_head "Roles"
ROLES="$(im_splunk_auth "search '| rest /services/authentication/users splunk_server=local
 | search title=\"$WHO\" | fields roles | mvexpand roles | table roles' -output csv -preview false" \
  | sed -n '2,$p' | tr -d '\r"' | grep . || true)"
if [ -n "$ROLES" ]; then
    printf '%s\n' "$ROLES" | sed 's/^/    /'
else
    im_warn "could not read the account's roles; it may lack rest access to"
    im_warn "/services/authentication/users. Capability checks below still work."
fi

im_head "Capabilities these scripts rely on"
CAPS="$(im_splunk_auth "search '| rest /services/authentication/current-context splunk_server=local
 | fields capabilities | mvexpand capabilities | table capabilities' -output csv -preview false" \
  | sed -n '2,$p' | tr -d '\r"' | grep . || true)"
NCAP="$(printf '%s\n' "$CAPS" | grep -c . || true)"
im_say "$(im_num "$NCAP") capabilities in total"
have() { printf '%s\n' "$CAPS" | grep -qx "$1" && return 0 || return 1; }
check_cap() {  # $1 capability, $2 what it is for
    if have "$1"; then printf '    yes  %-26s %s\n' "$1" "$2"
    else                printf '    NO   %-26s %s\n' "$1" "$2"; fi
}
check_cap search                "run any search at all"
check_cap indexes_edit          "create an index or change its retention"
check_cap can_delete            "mark events unsearchable with | delete"
check_cap admin_all_objects     "read and write other people's knowledge objects"
check_cap rest_properties_set   "reload configuration without a restart"
check_cap list_search_head_clustering "see the cluster, if there is one"
echo
im_say "'NO' is not a fault -- it means that operation needs a different"
im_say "account. can_delete in particular is withheld from admin by default."

# --- what the account can see ------------------------------------------
# srchIndexesAllowed decides what exists as far as a search is concerned,
# and srchIndexesDefault decides what a search with no index= term reaches.
im_head "Indexes this account may search"
ALLOWED="$(im_splunk_auth "search '| rest /services/authorization/roles splunk_server=local
 | fields title, srchIndexesAllowed, srchIndexesDefault
 | mvexpand srchIndexesAllowed | table title, srchIndexesAllowed' -output csv -preview false" \
  | sed -n '2,$p' | tr -d '\r"' | grep . || true)"
if [ -n "$ALLOWED" ]; then
    printf '%s\n' "$ALLOWED" | awk -F, '{printf "    %-20s %s\n", $1, $2}' | sort -u
else
    im_warn "could not read role index permissions"
fi

im_head "Searched by default, when a search names no index"
DEFAULT="$(im_splunk_auth "search '| rest /services/authorization/roles splunk_server=local
 | fields title, srchIndexesDefault | mvexpand srchIndexesDefault
 | table title, srchIndexesDefault' -output csv -preview false" \
  | sed -n '2,$p' | tr -d '\r"' | grep . || true)"
if [ -n "$DEFAULT" ]; then
    printf '%s\n' "$DEFAULT" | awk -F, '{printf "    %-20s %s\n", $1, $2}' | sort -u
    echo
    im_say "An index not listed here is invisible to a search that does not name"
    im_say "it. This is the usual reason data 'is not there' when it is."
else
    im_warn "could not read the default index list"
fi

# --- does it line up with what exists? ---------------------------------
im_head "Defined but not searchable by this account"
DEFINED="$(im_run "$IM_SPLUNK_HOME/bin/splunk btool indexes list 2>/dev/null \
            | sed -n 's/^\[\(.*\)\]$/\1/p' | grep -v '^default$' | grep -v ':' | sort")"
VISIBLE="$(im_splunk_auth "search '| eventcount summarize=false index=* index=_* | dedup index | table index' -output csv -preview false" \
  | sed -n '2,$p' | tr -d '\r"' | grep . | sort || true)"
if [ -n "$VISIBLE" ]; then
    MISSING="$(comm -23 <(printf '%s\n' "$DEFINED") <(printf '%s\n' "$VISIBLE") 2>/dev/null || true)"
    if [ -n "$MISSING" ]; then
        printf '%s\n' "$MISSING" | sed 's/^/    /'
        echo
        im_say "These are configured on the instance but this account cannot reach"
        im_say "them. That is a permissions answer, not a data answer."
    else
        im_say "none -- this account can reach every index defined here"
    fi
else
    im_warn "could not enumerate searchable indexes"
fi
echo

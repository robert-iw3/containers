#!/bin/bash
set -Eeuo pipefail

# CIS 4.4: Set ulimits for high connections (balance with perf)
ulimit -n 64000  # Open files
ulimit -u 64000  # Processes

if [ "${1:0:1}" = '-' ]; then
	set -- mongod "$@"
fi

originalArgOne="$1"

# allow the container to be started with `--user`
if [[ "$originalArgOne" == mongo* ]] && [ "$(id -u)" = '0' ]; then
	if [ "$originalArgOne" = 'mongod' ]; then
		find /data/configdb /data/db \! -user mongodb -exec chown mongodb '{}' +
	fi
	chown --dereference mongodb "/proc/$$/fd/1" "/proc/$$/fd/2" || :
	exec gosu mongodb "$BASH_SOURCE" "$@"
fi

dpkgArch="$(dpkg --print-architecture)"
case "$dpkgArch" in
	amd64)
		if ! grep -qE '^flags.* avx( .*|$)' /proc/cpuinfo; then
			echo >&2 'WARNING: MongoDB 8.0+ requires AVX support!'
		fi
		;;
	arm64)
		if ! grep -qE '^Features.* (fphp|dcpop|sha3|sm3|sm4|asimddp|sha512|sve)( .*|$)' /proc/cpuinfo; then
			echo >&2 'WARNING: MongoDB 8.0+ requires ARMv8.2-A or higher!'
		fi
		;;
esac

if [[ "$originalArgOne" == mongo* ]]; then
	numa='numactl --interleave=all'
	if command -v numactl >/dev/null && $numa true &> /dev/null; then
		set -- $numa "$@"
	fi
fi

file_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	local def="${2:-}"
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		echo >&2 "error: both $var and $fileVar are set (but are exclusive)"
		exit 1
	fi
	local val="$def"
	if [ "${!var:-}" ]; then
		val="${!var}"
	elif [ "${!fileVar:-}" ]; then
		val="$(< "${!fileVar}")"
	fi
	export "$var"="$val"
	unset "$fileVar"
}

_mongod_hack_have_arg() {
	local checkArg="$1"; shift
	for arg in "$@"; do
		case "$arg" in
			"$checkArg"|"$checkArg"=*) return 0 ;;
		esac
	done
	return 1
}

_mongod_hack_get_arg_val() {
	local checkArg="$1"; shift
	while [ $# -gt 0 ]; do
		case "$1" in
			"$checkArg")
				echo "$2"
				return 0
				;;
			"$checkArg"=?*)
				echo "${1#"$checkArg="}"
				return 0
				;;
		esac
		shift
	done
	return 1
}

declare -a mongodHackedArgs

_mongod_hack_ensure_arg() {
	local ensureArg="$1"; shift
	mongodHackedArgs=( "$@" )
	! _mongod_hack_have_arg "$ensureArg" "$@" && mongodHackedArgs+=( "$ensureArg" )
}

_mongod_hack_ensure_no_arg() {
	local ensureNoArg="$1"; shift
	mongodHackedArgs=()
	while [ $# -gt 0 ]; do
		[ "$1" != "$ensureNoArg" ] && mongodHackedArgs+=( "$1" )
		shift
	done
}

_mongod_hack_ensure_no_arg_val() {
	local ensureNoArg="$1"; shift
	mongodHackedArgs=()
	while [ $# -gt 0 ]; do
		case "$1" in
			"$ensureNoArg")
				shift # skip value
				;;
			"$ensureNoArg"=?*)
				# skip
				;;
			*)
				mongodHackedArgs+=( "$1" )
				;;
		esac
		shift
	done
}

_mongod_hack_ensure_arg_val() {
	local ensureArg="$1" ensureVal="$2"; shift 2
	_mongod_hack_ensure_no_arg_val "$ensureArg" "$@"
	mongodHackedArgs+=( "$ensureArg" "$ensureVal" )
}

_js_escape() {
	jq --null-input --arg str "$1" '$str | @jsstring'
}

: "${TMPDIR:=/tmp}"
jsonConfigFile="$TMPDIR/docker-entrypoint-config.json"
tempConfigFile="$TMPDIR/docker-entrypoint-temp-config.json"

_parse_config() {
	[ -s "$tempConfigFile" ] && return 0
	local configPath="$(_mongod_hack_get_arg_val --config "$@")"
	[ -s "$configPath" ] || return 1
	mongoShell='mongosh'
	command -v "$mongoShell" >/dev/null || mongoShell='mongo'
	if [ "$mongoShell" = 'mongosh' ]; then
		"$mongoShell" --norc --nodb --quiet --eval "load('/js-yaml.js'); JSON.stringify(jsyaml.load(fs.readFileSync($(_js_escape "$configPath"), 'utf8')))" > "$jsonConfigFile"
	else
		"$mongoShell" --norc --nodb --quiet --eval "load('/js-yaml.js'); printjson(jsyaml.load(cat($(_js_escape "$configPath"))))" > "$jsonConfigFile"
	fi
	[ "$(head -c1 "$jsonConfigFile")" = '{' ] && [ "$(tail -c2 "$jsonConfigFile")" = '}' ] || { cat >&2 "$jsonConfigFile"; exit 1; }
	jq 'del(.systemLog, .processManagement, .net, .security, .replication)' "$jsonConfigFile" > "$tempConfigFile"
}

dbPath=
_dbPath() {
	[ -n "$dbPath" ] && echo "$dbPath" && return
	dbPath="$(_mongod_hack_get_arg_val --dbpath "$@")"
	_parse_config "$@" && dbPath="$(jq -r '.storage.dbPath // empty' "$jsonConfigFile")"
	[ -z "$dbPath" ] && (_mongod_hack_have_arg --configsvr "$@" || { _parse_config "$@" && [ "$(jq -r '.sharding.clusterRole // empty' "$jsonConfigFile")" = 'configsvr' ]; }) && dbPath=/data/configdb
	: "${dbPath:=/data/db}"
	echo "$dbPath"
}

if [ "$originalArgOne" = 'mongod' ]; then
	file_env 'MONGO_INITDB_ROOT_USERNAME'
	file_env 'MONGO_INITDB_ROOT_PASSWORD'

	mongoShell='mongosh'
	command -v "$mongoShell" >/dev/null || mongoShell='mongo'

	shouldPerformInitdb=
	[ "$MONGO_INITDB_ROOT_USERNAME" ] && [ "$MONGO_INITDB_ROOT_PASSWORD" ] && { _mongod_hack_ensure_arg '--auth' "$@"; set -- "${mongodHackedArgs[@]}"; shouldPerformInitdb=true; } || {
		[ "$MONGO_INITDB_ROOT_USERNAME" ] || [ "$MONGO_INITDB_ROOT_PASSWORD" ] && { echo >&2 "error: both MONGO_INITDB_ROOT_USERNAME and MONGO_INITDB_ROOT_PASSWORD must be set"; exit 1; }
	}
	[ -z "$shouldPerformInitdb" ] && for f in /docker-entrypoint-initdb.d/*; do case "$f" in *.sh|*.js) shouldPerformInitdb="$f"; break;; esac; done

	[ -n "$shouldPerformInitdb" ] && {
		dbPath="$(_dbPath "$@")"
		for path in "$dbPath/WiredTiger" "$dbPath/journal" "$dbPath/local.0" "$dbPath/storage.bson"; do [ -e "$path" ] && shouldPerformInitdb= && break; done
	}

	[ -n "$shouldPerformInitdb" ] && {
		mongodHackedArgs=( "$@" )
		_parse_config "$@" && _mongod_hack_ensure_arg_val --config "$tempConfigFile" "${mongodHackedArgs[@]}"
		_mongod_hack_ensure_arg_val --bind_ip 127.0.0.1 "${mongodHackedArgs[@]}"
		_mongod_hack_ensure_arg_val --port 27017 "${mongodHackedArgs[@]}"
		_mongod_hack_ensure_no_arg --bind_ip_all "${mongodHackedArgs[@]}"
		_mongod_hack_ensure_no_arg --auth "${mongodHackedArgs[@]}"
		_mongod_hack_ensure_no_arg_val --keyFile "${mongodHackedArgs[@]}"
		[ "$MONGO_INITDB_ROOT_USERNAME" ] && [ "$MONGO_INITDB_ROOT_PASSWORD" ] && _mongod_hack_ensure_no_arg_val --replSet "${mongodHackedArgs[@]}"

		tlsMode='disabled'
		_mongod_hack_have_arg --tlsCertificateKeyFile "$@" && tlsMode='requireTLS'
		_mongod_hack_ensure_arg_val --tlsMode "$tlsMode" "${mongodHackedArgs[@]}"

		if [ -w "/proc/$$/fd/1" ]; then
			_mongod_hack_ensure_arg_val --logpath "/proc/$$/fd/1" "${mongodHackedArgs[@]}"
		else
			initdbLogPath="$(_dbPath "$@")/docker-initdb.log"
			echo >&2 "warning: initdb logs to '$initdbLogPath'"
			_mongod_hack_ensure_arg_val --logpath "$initdbLogPath" "${mongodHackedArgs[@]}"
		fi
		_mongod_hack_ensure_arg --logappend "${mongodHackedArgs[@]}"
		_mongod_hack_ensure_arg_val --pidfilepath "$TMPDIR/docker-entrypoint-temp-mongod.pid" "${mongodHackedArgs[@]}"

		"${mongodHackedArgs[@]}" --fork

		mongo=( "$mongoShell" --host 127.0.0.1 --port 27017 --quiet )

		tries=30
		while true; do
			pidfile="$TMPDIR/docker-entrypoint-temp-mongod.pid"
			[ -s "$pidfile" ] && ps "$(cat "$pidfile")" &>/dev/null || { echo >&2 "error: mongod not running"; exit 1; }
			"${mongo[@]}" --eval 'db.adminCommand("ping")' &>/dev/null && break
			((tries--)) || { echo >&2 "error: mongod not accepting connections"; exit 1; }
			sleep 1
		done

		[ "$MONGO_INITDB_ROOT_USERNAME" ] && [ "$MONGO_INITDB_ROOT_PASSWORD" ] && {
			rootAuthDatabase='admin'
			"${mongo[@]}" "$rootAuthDatabase" --eval "db.createUser({user: $(_js_escape "$MONGO_INITDB_ROOT_USERNAME"), pwd: $(_js_escape "$MONGO_INITDB_ROOT_PASSWORD"), roles: [{role: 'root', db: $(_js_escape "$rootAuthDatabase")}]})"
		}

		[ "${MONGO_INITDB_REPLSET:-}" ] && {
			"${mongo[@]}" --eval "rs.initiate({_id: $(_js_escape "${MONGO_INITDB_REPLSET}"), members: [{_id: 0, host: 'localhost:27017'}]})"
			echo "Replica set '${MONGO_INITDB_REPLSET}' initialized."
		}

		MONGO_INITDB_DATABASE="${MONGO_INITDB_DATABASE:-test}"
		for f in /docker-entrypoint-initdb.d/*; do
			case "$f" in
				*.sh) echo "$0: running $f"; . "$f" ;;
				*.js) echo "$0: running $f"; "${mongo[@]}" "$MONGO_INITDB_DATABASE" --file "$f"; echo ;;
				*) echo "$0: ignoring $f" ;;
			esac
			echo
		done

		"${mongodHackedArgs[@]}" --shutdown
		rm -f "$TMPDIR/docker-entrypoint-temp-mongod.pid"
		echo 'MongoDB init complete; ready for start up.'
		echo
	}
	haveBindIp=
	_mongod_hack_have_arg --bind_ip "$@" || _mongod_hack_have_arg --bind_ip_all "$@" && haveBindIp=1
	_parse_config "$@" && jq --exit-status '.net.bindIp // .net.bindIpAll' "$jsonConfigFile" >/dev/null && haveBindIp=1
	[ -z "$haveBindIp" ] && set -- "$@" --bind_ip_all

	unset "${!MONGO_INITDB_@}"
fi

rm -f "$jsonConfigFile" "$tempConfigFile"

exec "$@"
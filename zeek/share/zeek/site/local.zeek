##! Local site policy for Zeek network monitoring
##! Customizes protocol analysis, logging, and security settings
##! See https://docs.zeek.org/en/stable/script-reference/scripts.html

# Validate environment variables
function sanitize_env_var(name: string, regex: pattern, default_val: string): string {
    local val = getenv(name);
    if (val == "" || !val in regex) {
        print fmt("Warning: Invalid %s value '%s', using default '%s'", name, val, default_val);
        return default_val;
    }
    return val;
}

global true_regex: pattern = /^\s*(?i:t(rue)?|y(es)?|on|1)\s*$/;
global ip_regex: pattern = /^([0-9]{1,3}\.){3}[0-9]{1,3}(\/[0-9]{1,2})?(,([0-9]{1,3}\.){3}[0-9]{1,3}(\/[0-9]{1,2})?)*$/;

global disable_stats = (sanitize_env_var("ZEEK_DISABLE_STATS", true_regex, "false") == true_regex) ? T : F;
global disable_hash_all_files = (sanitize_env_var("ZEEK_DISABLE_HASH_ALL_FILES", true_regex, "false") == true_regex) ? T : F;
global disable_log_passwords = (sanitize_env_var("ZEEK_DISABLE_LOG_PASSWORDS", true_regex, "true") == true_regex) ? T : F;
global disable_ssl_validate_certs = (sanitize_env_var("ZEEK_DISABLE_SSL_VALIDATE_CERTS", true_regex, "false") == true_regex) ? T : F;
global disable_track_all_assets = (sanitize_env_var("ZEEK_DISABLE_TRACK_ALL_ASSETS", true_regex, "false") == true_regex) ? T : F;
global disable_best_guess_ics = (sanitize_env_var("ZEEK_DISABLE_BEST_GUESS_ICS", true_regex, "false") == true_regex) ? T : F;
global disable_detect_routers = (sanitize_env_var("ZEEK_DISABLE_DETECT_ROUTERS", true_regex, "false") == true_regex) ? T : F;
global zeek_local_nets_str = sanitize_env_var("ZEEK_LOCAL_NETS", ip_regex, "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16");

redef Broker::default_listen_address = "127.0.0.1";
redef ignore_checksums = T;

global capture_filter_str = sanitize_env_var("CAPTURE_FILTER", /^[\w\s\(\)\/|&!=><-]+$/ , "");
@if (capture_filter_str != "")
  redef restrict_filters += { ["user-defined capture filter"] = capture_filter_str };
@endif

global json_format = (sanitize_env_var("ZEEK_JSON", true_regex, "true") == true_regex) ? T : F;
@if (json_format)
  redef LogAscii::use_json = T;
@endif

@load frameworks/software/vulnerable
@load frameworks/software/version-changes
@load frameworks/software/windows-version-detection
@load-sigs frameworks/signatures/detect-windows-shells
@load protocols/conn/known-hosts
@load protocols/conn/known-services
@load protocols/dhcp/software
@load protocols/dns/detect-external-names
@load protocols/ftp/detect
@load protocols/ftp/detect-bruteforcing.zeek
@load protocols/ftp/software
@load protocols/http/detect-sqli
@load protocols/http/detect-webapps
@load protocols/http/header-names
@load protocols/http/software
@load protocols/http/software-browser-plugins
@load protocols/mysql/software
@load protocols/ssl/weak-keys
@load protocols/smb/log-cmds
@load protocols/smtp/software
@load protocols/ssh/detect-bruteforcing
@load protocols/ssh/geo-data
@load protocols/ssh/interesting-hostnames
@load protocols/ssh/software
@load protocols/ssl/known-certs
@load protocols/ssl/log-hostcerts-only
@if (!disable_ssl_validate_certs)
  @load protocols/ssl/validate-certs
@endif
@if (!disable_track_all_assets)
  @load tuning/track-all-assets.zeek
@endif
@if (!disable_hash_all_files)
  @load frameworks/files/hash-all-files
@endif
@if (!disable_stats)
  @load policy/misc/stats
  @load policy/misc/capture-loss
@endif
@load policy/protocols/conn/vlan-logging
@load policy/protocols/conn/mac-logging
@load policy/protocols/modbus/known-masters-slaves
@load policy/frameworks/notice/community-id
@load ./login.zeek

@if (!disable_best_guess_ics)
 @load ./guess.zeek
@endif
@if (!disable_detect_routers)
  @load ./known-routers.zeek
@endif
@if (sanitize_env_var("ZEEK_ENABLE_ICS", true_regex, "false") == true_regex)
  @load ACID/scripts
  @load icsnpp-bacnet
  @load icsnpp-modbus
@endif

@load packages
@load intel
@load custom
@load policy/tuning/json-logs.zeek

# Conditional logging for ICS protocols
global log_bsap = (sanitize_env_var("ZEEK_LOG_BSAP", true_regex, "false") == true_regex) ? T : F;
global log_ecat_arp = (sanitize_env_var("ZEEK_LOG_ECAT_ARP", true_regex, "false") == true_regex) ? T : F;

@if (!log_bsap)
  hook Bsap::log_policy_bsap_ip_unknown(rec: Bsap::BSAP_IP_UNKNOWN, id: Log::ID, filter: Log::Filter) { break; }
  hook Bsap::log_policy_bsap_serial_unknown(rec: Bsap::BSAP_SERIAL_UNKNOWN, id: Log::ID, filter: Log::Filter) { break; }
@endif
@if (!log_ecat_arp)
  hook PacketAnalyzer::ECAT::log_policy_ecat_arp(rec: PacketAnalyzer::ECAT::ECAT_ARP_INFO, id: Log::ID, filter: Log::Filter) { break; }
@endif

event zeek_init() &priority=-5 {
  if (zeek_local_nets_str != "") {
    local nets_strs = split_string(zeek_local_nets_str, /,/);
    if (|nets_strs| > 0) {
      for (net_idx in nets_strs) {
        local local_subnet = to_subnet(nets_strs[net_idx]);
        if (local_subnet != [::]/0) {
          add Site::local_nets[local_subnet];
        }
      }
    }
  }
}

@if (!disable_log_passwords)
  redef HTTP::default_capture_password = T;
  redef FTP::default_capture_password = T;
  redef SOCKS::default_capture_password = T;
@else
  redef HTTP::default_capture_password = F;
  redef FTP::default_capture_password = F;
  redef SOCKS::default_capture_password = F;
@endif
redef HTTP::log_client_header_names = T;
redef HTTP::log_server_header_names = T;
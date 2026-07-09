##! Logs routers detected by packets with TTL/HLIM 255, once per interval (default: 1 day)
##! Modeled after known-hosts.zeek

@load base/utils/directions-and-hosts
@load base/frameworks/cluster

module Known;

export {
  redef enum Log::ID += { ROUTERS_LOG };

  global log_policy_routers: Log::PolicyHook;

  type RouterInfo: record {
    ts: time &log;
    orig_h: addr &log;
    orig_l2_addr: string &log &default="unknown";
    ttl: count &log &optional;
    hlim: count &log &optional;
  };

  const use_router_store = F &redef;
  option router_tracking = LOCAL_HOSTS;
  global router_store: Cluster::StoreInfo;
  const router_store_name = "zeek/known/routers" &redef;
  option router_store_expiry = 1day &redef;
  option router_store_timeout = 15sec;
  global routers: set[addr] &create_expire=router_store_expiry &redef;

  global log_known_routers: event(rec: RouterInfo);
}

event zeek_init() {
  if (!use_router_store) return;
  router_store = Cluster::create_store(router_store_name);
}

event router_found(info: RouterInfo) {
  if (!use_router_store) return;
  when [info] (local r = Broker::put_unique(router_store$store, info$orig_h, T, router_store_expiry)) {
    if (r$status == Broker::SUCCESS && r$result as bool) {
      Log::write(ROUTERS_LOG, info);
    } else {
      Reporter::error(fmt("%s: data store put_unique failure", router_store_name));
    }
  } timeout router_store_timeout {
    Log::write(ROUTERS_LOG, info);
  }
}

event known_router_add(info: RouterInfo) {
  if (use_router_store) return;
  if (info$orig_h in routers) return;
  add routers[info$orig_h];
  @if (!Cluster::is_enabled() || Cluster::local_node_type() == Cluster::PROXY)
    Log::write(ROUTERS_LOG, info);
  @endif
}

event Cluster::node_up(name: string, id: string) {
  if (use_router_store || Cluster::local_node_type() != Cluster::WORKER) return;
  clear_table(routers);
}

event Cluster::node_down(name: string, id: string) {
  if (use_router_store || Cluster::local_node_type() != Cluster::WORKER) return;
  clear_table(routers);
}

event router_found(info: RouterInfo) {
  if (use_router_store) return;
  if (info$orig_h in routers) return;
  Cluster::publish_hrw(Cluster::proxy_pool, info$orig_h, known_router_add, info);
  event known_router_add(info);
}

event zeek_init() &priority=5 {
  Log::create_stream(ROUTERS_LOG, [$columns=RouterInfo, $ev=log_known_routers, $path="known_routers", $policy=log_policy_routers]);
}

event new_connection(c: connection) &priority=5 {
  local p: raw_pkt_hdr = get_current_packet_header();
  if (((p?$ip && p$ip$ttl == 255) || (p?$ip6 && p$ip6$hlim == 255)) && addr_matches_host(c$id$orig_h, router_tracking)) {
    local ttl: count = p?$ip ? p$ip$ttl : 0;
    local hlim: count = p?$ip6 ? p$ip6$hlim : 0;
    local mac: string = c?$orig && c$orig?$l2_addr ? c$orig$l2_addr : "unknown";
    event router_found([$ts=network_time(), $orig_h=c$id$orig_h, $ttl=ttl, $hlim=hlim, $orig_l2_addr=mac]);
  }
}
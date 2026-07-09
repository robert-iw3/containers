##! Logs telnet, rlogin, and rsh events to login.log
##! Tracks authentication attempts and outcomes

module Login;

export {
  redef enum Log::ID += { Log_LOGIN };

  type Info: record {
    ts: time &log;
    uid: string &log;
    id: conn_id &log;
    proto: string &log &optional;
    success: bool &log &default=F;
    confused: bool &log &default=F;
    user: string &log &optional;
    client_user: string &log &optional;
    password: string &log &optional;
    logged: bool &default=F;
  };

  global log_login: event(rec: Info);
}

redef record connection += { login: Info &optional; };

# Configurable ports
const login_ports: table[port] of string = {
  [23/tcp] = "telnet",
  [513/tcp] = "rlogin",
  [514/tcp] = "rsh"
} &redef;
redef likely_server_ports += { [23/tcp], [513/tcp], [514/tcp] };

const skip_authentication: set[string] = { "WELCOME TO THE BERKELEY PUBLIC LIBRARY" } &redef;
const direct_login_prompts: set[string] = { "TERMINAL?" } &redef;
const login_prompts: set[string] = {
  "Login:", "login:", "Name:", "Username:", "User:", "Member Name",
  "User Access Verification", "Cisco Systems Console"
} &redef;
const login_non_failure_msgs: set[string] = {
  "Failures", "failures", "failure since last successful login",
  "failures since last successful login"
} &redef;
const login_failure_msgs: set[string] = {
  "invalid", "Invalid", "incorrect", "Incorrect", "failure", "Failure",
  "User authorization failure", "Login failed", "INVALID", "Sorry.", "Sorry,"
} &redef;
const router_prompts: set[string] = {} &redef;
const login_success_msgs: set[string] = {
  "Last login", "Last successful login", "Last   successful login",
  "checking for disk quotas", "unsuccessful login attempts",
  "failure since last successful login", "failures since last successful login"
} &redef;
const login_timeouts: set[string] = {
  "timeout", "timed out", "Timeout", "Timed out", "Error reading command input"
} &redef;

function set_login_session(c: connection) {
  if (!c?$login) {
    local s: Info = [$ts=network_time(), $uid=c$uid, $id=c$id];
    if (c$id$resp_p in login_ports) {
      s$proto = login_ports[c$id$resp_p];
      add c$service[login_ports[c$id$resp_p]];
    }
    c$login = s;
  }
}

function login_message(s: Info) {
  if ((s?$user) && (s$user in ["", "<none>", "<timeout>"])) delete s$user;
  if ((s?$client_user) && (s$client_user in ["", "<none>", "<timeout>"])) delete s$client_user;
  if ((s?$password) && (s$password in ["", "<none>", "<timeout>"])) delete s$password;
  if ((s?$proto) && (s$proto == "")) delete s$proto;

  s$ts = network_time();
  Log::write(Login::Log_LOGIN, s);
  s$logged = T;
}

event zeek_init() &priority=5 {
  Log::create_stream(Login::Log_LOGIN, [$columns=Info, $ev=log_login, $path="login"]);
  for (p in login_ports) {
    Analyzer::register_for_ports(Analyzer::ANALYZER_TELNET, {p});
    Analyzer::register_for_ports(Analyzer::ANALYZER_RLOGIN, {p});
    Analyzer::register_for_ports(Analyzer::ANALYZER_RSH, {p});
  }
}

event login_confused(c: connection, msg: string, line: string) &priority=5 {
  set_login_session(c);
  c$login$confused = T;
}

event login_failure(c: connection, user: string, client_user: string, password: string, line: string) &priority=5 {
  set_login_session(c);
  if ((!c$login?$user) || (c$login$user == "")) c$login$user = user;
  if ((!c$login?$client_user) || (c$login$client_user == "")) c$login$client_user = client_user;
  if ((!c$login?$password) || (c$login$password == "")) c$login$password = password;
  login_message(c$login);
}

event login_success(c: connection, user: string, client_user: string, password: string, line: string) &priority=5 {
  set_login_session(c);
  c$login$success = T;
  c$login$user = user;
  c$login$client_user = client_user;
  if ((c$login$proto != "rsh") || (c$login$client_user == "")) c$login$password = password;
  login_message(c$login);
}

event connection_state_remove(c: connection) &priority=-5 {
  if (c?$login && c$login$logged == F) {
    login_message(c$login);
    delete c$login;
  }
}

@if (getenv("ZEEK_DEBUG_LOGIN") == "true")
  event authentication_accepted(name: string, c: connection) { print "authentication_accepted", name; }
  event authentication_rejected(name: string, c: connection) { print "authentication_rejected", name; }
  # ... other debug events
@endif
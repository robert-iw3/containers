##! Guesses protocols based on transport protocol, destination port, and source port
##! Logs results to bestguess.log using a mapping file (guess_ics_map.txt)

module Best_Guess;

export {
  redef enum Log::ID += { BEST_GUESS_LOG };

  type Best_Guess_Key: record {
    proto: transport_proto &optional;
    dport: count &optional;
    sport: count &optional;
  };

  type Best_Guess_Value: record {
    name: string &optional;
    category: string &optional;
  };

  type Info: record {
    ts: time &log;
    uid: string &log;
    id: conn_id &log;
    proto: transport_proto &log &optional;
    name: string &log &optional;
    category: string &log &optional;
    guess_info: Best_Guess_Value &optional;
  };

  global log_best_guess: event(rec: Info);
}

global proto_guesses: table[transport_proto, count, count] of Best_Guess_Value = table();
global guest_map_filespec: string = @DIR + "/guess_ics_map.txt";

event zeek_init() &priority=5 {
  if (!file_exists(guest_map_filespec)) {
    print "Warning: guess_ics_map.txt not found, skipping protocol guessing";
    return;
  }
  Input::add_table([$source=guest_map_filespec, $name="guess_ics_map",
                    $idx=Best_Guess_Key, $val=Best_Guess_Value,
                    $destination=proto_guesses, $want_record=T]);
  Input::remove("guess_ics_map");
  Log::create_stream(BEST_GUESS_LOG, [$columns=Info, $ev=log_best_guess, $path="bestguess"]);
}

event connection_state_remove(c: connection) {
  local p = get_port_transport_proto(c$id$resp_p);
  local dp = port_to_count(c$id$resp_p);
  local sp = port_to_count(c$id$orig_p);
  local guess = Best_Guess_Value($name="");
  local category: string = "";

  if (((!c?$service) || (|c$service| == 0)) && (p != icmp)) {
    if ([p, dp, sp] in proto_guesses) guess = proto_guesses[p, dp, sp];
    else if ([p, dp, 0] in proto_guesses) guess = proto_guesses[p, dp, 0];
    else if ([p, 0, sp] in proto_guesses) guess = proto_guesses[p, 0, sp];
    else if ([unknown_transport, dp, sp] in proto_guesses) guess = proto_guesses[unknown_transport, dp, sp];
    else if ([unknown_transport, dp, 0] in proto_guesses) guess = proto_guesses[unknown_transport, dp, 0];
    else if ([unknown_transport, 0, sp] in proto_guesses) guess = proto_guesses[unknown_transport, 0, sp];

    if (guess?$name && guess$name != "") {
      if (guess?$category) category = guess$category;
      Log::write(BEST_GUESS_LOG, [$ts=network_time(), $uid=c$uid, $id=c$id, $proto=p, $name=guess$name, $category=category, $guess_info=guess]);
    }
  } else if (p == icmp) {
    print "Skipping ICMP connection for protocol guessing";
  }
}
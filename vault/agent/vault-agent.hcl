pid_file = "./vault-agent.pid"

vault {
  address = "https://127.0.0.1:8200"
  retry {
    num_retries = 5
  }
}

auto_auth {
    method {
        type = "approle"
        config = {
            role_id_file_path = "./role_id"
            secret_id_file_path = "./secret_id"
            remove_secret_id_file_after_reading = false
        }
    }

    sink {
        type = "file"
        config = {
            path = "./vault-agent-token"
        }
    }
}

template {
  source      = "./env-template.tmpl"
  destination = "./.env"
}

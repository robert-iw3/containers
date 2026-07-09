import pytest

import deploy


def base_ansible_config(server_count=3):
    return {
        "cluster_name": "test",
        "avenue": "ansible",
        "ansible": {
            "servers": [
                {"name": f"server-{i}", "address": f"10.0.0.{i}"}
                for i in range(1, server_count + 1)
            ],
            "clients": [{"name": "client-1", "address": "10.0.1.1"}],
        },
        "features": {"bootstrap_expect": server_count},
    }


def base_terraform_config():
    return {
        "cluster_name": "test",
        "avenue": "terraform",
        "terraform": {"region": "us-east-1", "ssl_cert_arn": "arn:aws:acm:us-east-1:1:certificate/x"},
        "features": {"bootstrap_expect": 3},
    }


class TestRequireOddQuorum:
    @pytest.mark.parametrize("count", [1, 3, 5])
    def test_accepts_odd_counts(self, count):
        deploy._require_odd_quorum(count, "label")

    @pytest.mark.parametrize("count", [0, 2, 4])
    def test_rejects_even_or_zero_counts(self, count):
        with pytest.raises(deploy.ConfigError):
            deploy._require_odd_quorum(count, "label")


class TestValidateConfigCommon:
    def test_empty_config_rejected(self):
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config({})

    def test_missing_avenue_rejected(self):
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config({"cluster_name": "x"})

    def test_unknown_avenue_rejected(self):
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config({"avenue": "kubernetes"})


class TestValidateConfigAnsible:
    def test_valid_config_passes(self):
        deploy.validate_config(base_ansible_config())

    def test_missing_ansible_section_rejected(self):
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config({"avenue": "ansible"})

    def test_no_servers_rejected(self):
        config = base_ansible_config()
        config["ansible"]["servers"] = []
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_server_count_must_match_bootstrap_expect(self):
        config = base_ansible_config(server_count=3)
        config["features"]["bootstrap_expect"] = 5
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_even_server_count_rejected(self):
        config = base_ansible_config(server_count=2)
        config["features"]["bootstrap_expect"] = 2
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_client_host_missing_name_rejected(self):
        config = base_ansible_config()
        config["ansible"]["clients"].append({"address": "10.0.0.99"})
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_server_host_missing_name_rejected(self):
        # Append two malformed hosts (not one) so the server count stays odd
        # and the quorum check doesn't mask the per-host validation being tested.
        config = base_ansible_config(server_count=3)
        config["ansible"]["servers"].append({"address": "10.0.0.98"})
        config["ansible"]["servers"].append({"address": "10.0.0.99"})
        config["features"]["bootstrap_expect"] = 5
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_host_missing_address_rejected(self):
        config = base_ansible_config()
        config["ansible"]["clients"].append({"name": "client-2"})
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)


class TestValidateConfigTerraform:
    def test_valid_config_passes(self):
        deploy.validate_config(base_terraform_config())

    def test_missing_terraform_section_rejected(self):
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config({"avenue": "terraform"})

    def test_missing_region_rejected(self):
        config = base_terraform_config()
        del config["terraform"]["region"]
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_missing_ssl_cert_arn_rejected(self):
        config = base_terraform_config()
        del config["terraform"]["ssl_cert_arn"]
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)

    def test_even_server_count_rejected(self):
        config = base_terraform_config()
        config["terraform"]["server_count"] = 4
        with pytest.raises(deploy.ConfigError):
            deploy.validate_config(config)


class TestRenderInventory:
    def test_contains_all_groups_and_hosts(self):
        inventory = deploy.render_inventory(base_ansible_config())
        assert "[nomad_servers]" in inventory
        assert "[nomad_clients]" in inventory
        assert "[nomad_cluster:children]" in inventory
        assert "server-1 ansible_host=10.0.0.1" in inventory
        assert "client-1 ansible_host=10.0.1.1" in inventory

    def test_defaults_ssh_user_and_key(self):
        inventory = deploy.render_inventory(base_ansible_config())
        assert "ansible_user=ansible" in inventory
        assert "ansible_ssh_private_key_file=~/.ssh/id_rsa" in inventory

    def test_custom_ssh_user_and_key(self):
        config = base_ansible_config()
        config["ansible"]["ssh_user"] = "ec2-user"
        config["ansible"]["ssh_private_key"] = "/keys/custom.pem"
        inventory = deploy.render_inventory(config)
        assert "ansible_user=ec2-user" in inventory
        assert "ansible_ssh_private_key_file=/keys/custom.pem" in inventory


class TestRenderGroupVars:
    def test_defaults(self):
        group_vars = deploy.render_group_vars({})
        assert group_vars["nomad_tls_enabled"] is True
        assert group_vars["nomad_acl_enabled"] is True
        assert group_vars["nomad_gossip_encryption_enabled"] is True
        assert group_vars["nomad_vault_enabled"] is False
        assert group_vars["nomad_consul_enabled"] is False
        assert group_vars["nomad_podman_enabled"] is True
        assert group_vars["nomad_bootstrap_expect"] == 3

    def test_overrides(self):
        config = {
            "features": {
                "tls_enabled": False,
                "acl_enabled": False,
                "vault_enabled": True,
                "consul_enabled": True,
                "bootstrap_expect": 5,
            }
        }
        group_vars = deploy.render_group_vars(config)
        assert group_vars["nomad_tls_enabled"] is False
        assert group_vars["nomad_acl_enabled"] is False
        assert group_vars["nomad_vault_enabled"] is True
        assert group_vars["nomad_consul_enabled"] is True
        assert group_vars["nomad_bootstrap_expect"] == 5


class TestRenderTfvars:
    def test_keys_match_real_terraform_variables(self):
        tfvars = deploy.render_tfvars(base_terraform_config())
        # These must match variable names actually declared in terraform/variables.tf;
        # a mismatch here means the value is silently dropped at apply time.
        expected_keys = {
            "aws_region",
            "secondary_region",
            "cluster_name",
            "num_nomad_servers",
            "num_nomad_clients",
            "ssl_certificate_arn",
            "vault_enabled",
            "consul_enabled",
            "admin_cidr_blocks",
        }
        assert set(tfvars.keys()) == expected_keys

    def test_no_stale_keys_with_no_matching_variable(self):
        tfvars = deploy.render_tfvars(base_terraform_config())
        for stale_key in ("server_count", "client_count", "ssl_cert_arn", "tls_enabled", "acl_enabled"):
            assert stale_key not in tfvars

    def test_secondary_region_defaults_to_primary(self):
        tfvars = deploy.render_tfvars(base_terraform_config())
        assert tfvars["secondary_region"] == "us-east-1"

    def test_explicit_secondary_region(self):
        config = base_terraform_config()
        config["terraform"]["secondary_region"] = "us-west-2"
        tfvars = deploy.render_tfvars(config)
        assert tfvars["secondary_region"] == "us-west-2"

    def test_server_and_client_counts(self):
        config = base_terraform_config()
        config["terraform"]["server_count"] = 5
        config["terraform"]["client_count"] = 4
        tfvars = deploy.render_tfvars(config)
        assert tfvars["num_nomad_servers"] == 5
        assert tfvars["num_nomad_clients"] == 4

    def test_vault_and_consul_default_true(self):
        config = base_terraform_config()
        tfvars = deploy.render_tfvars(config)
        assert tfvars["vault_enabled"] is True
        assert tfvars["consul_enabled"] is True

    def test_vault_and_consul_can_be_disabled(self):
        config = base_terraform_config()
        config["features"]["vault_enabled"] = False
        config["features"]["consul_enabled"] = False
        tfvars = deploy.render_tfvars(config)
        assert tfvars["vault_enabled"] is False
        assert tfvars["consul_enabled"] is False


class TestMainCli:
    def test_validate_only_success(self, tmp_path, capsys):
        config_path = tmp_path / "cluster.yml"
        config_path.write_text(
            "avenue: ansible\n"
            "ansible:\n"
            "  servers:\n"
            "    - {name: s1, address: 10.0.0.1}\n"
            "features:\n"
            "  bootstrap_expect: 1\n"
        )
        rc = deploy.main(["--config", str(config_path), "--validate-only"])
        assert rc == 0
        assert "valid" in capsys.readouterr().out

    def test_validate_only_reports_error(self, tmp_path, capsys):
        config_path = tmp_path / "cluster.yml"
        config_path.write_text("avenue: nope\n")
        rc = deploy.main(["--config", str(config_path), "--validate-only"])
        assert rc == 1
        assert "invalid cluster.yml" in capsys.readouterr().err

    def test_missing_config_file_reports_error(self, tmp_path, capsys):
        rc = deploy.main(["--config", str(tmp_path / "does-not-exist.yml"), "--validate-only"])
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_dry_run_ansible_generates_files_without_running(self, tmp_path):
        config_path = tmp_path / "cluster.yml"
        config_path.write_text(
            "avenue: ansible\n"
            "ansible:\n"
            "  servers:\n"
            "    - {name: s1, address: 10.0.0.1}\n"
            "features:\n"
            "  bootstrap_expect: 1\n"
        )
        work_dir = tmp_path / "work"
        rc = deploy.main(
            ["--config", str(config_path), "--dry-run", "--work-dir", str(work_dir)]
        )
        assert rc == 0
        assert (work_dir / "inventory.ini").exists()
        assert (work_dir / "group_vars_all.yml").exists()

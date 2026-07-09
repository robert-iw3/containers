import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))

import ship


class TestValidation:
    @pytest.mark.parametrize("image", [
        "ghcr.io/org/app:abc123",
        "docker.io/library/nginx:1.27",
        "registry.example.com/team/app@sha256:" + "a" * 64,
        "app:latest",
    ])
    def test_valid_images(self, image):
        ship.validate_image(image)

    @pytest.mark.parametrize("image", [
        "ghcr.io/org/app:tag with spaces",
        "UPPERCASE/app:1",
        "app:tag;rm -rf /",
        "",
    ])
    def test_invalid_images_rejected(self, image):
        with pytest.raises(ship.ShipError):
            ship.validate_image(image)

    @pytest.mark.parametrize("name", ["app", "my-app-2", "a"])
    def test_valid_names(self, name):
        ship.validate_name(name)

    @pytest.mark.parametrize("name", ["My-App", "app_1", "-app", "a" * 64, ""])
    def test_invalid_names_rejected(self, name):
        with pytest.raises(ship.ShipError):
            ship.validate_name(name)


class TestRenderJob:
    def deploy_args(self, **overrides):
        defaults = dict(
            image="ghcr.io/org/app:v1", name="app", job=None, port=8080,
            count=2, cpu=200, memory=256, datacenter="dc1", driver="podman",
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_template_substitution_is_complete(self):
        hcl = ship.render_job(self.deploy_args())
        assert "__" not in hcl
        assert 'job "app"' in hcl
        assert 'image = "ghcr.io/org/app:v1"' in hcl
        assert "count = 2" in hcl
        assert "to = 8080" in hcl
        assert 'driver = "podman"' in hcl

    def test_update_stanza_present_for_auto_revert(self):
        hcl = ship.render_job(self.deploy_args())
        assert "auto_revert" in hcl

    def test_custom_job_substitutes_image_only(self, tmp_path):
        job_file = tmp_path / "custom.nomad.hcl"
        job_file.write_text('job "x" { image = "__IMAGE__" custom = true }')
        args = self.deploy_args(job=str(job_file))
        hcl = ship.render_job(args)
        assert 'image = "ghcr.io/org/app:v1"' in hcl
        assert "custom = true" in hcl


class TestContainerRuntime:
    def test_prefers_podman(self):
        with patch("shutil.which", side_effect=lambda r: f"/usr/bin/{r}"):
            assert ship.container_runtime() == "podman"

    def test_falls_back_to_docker(self):
        with patch("shutil.which", side_effect=lambda r: "/usr/bin/docker" if r == "docker" else None):
            assert ship.container_runtime() == "docker"

    def test_errors_when_neither_present(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(ship.ShipError):
                ship.container_runtime()


class TestNomadClient:
    def test_requires_nomad_addr(self, monkeypatch):
        monkeypatch.delenv("NOMAD_ADDR", raising=False)
        with pytest.raises(ship.ShipError):
            ship.NomadClient()

    def test_http_addr_needs_no_tls_context(self, monkeypatch):
        monkeypatch.setenv("NOMAD_ADDR", "http://127.0.0.1:4646")
        client = ship.NomadClient()
        assert client.ctx is None

    def test_https_with_cacert_verifies(self, monkeypatch, tmp_path):
        import subprocess
        key = tmp_path / "k.pem"
        crt = tmp_path / "c.pem"
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(key), "-out", str(crt), "-days", "1", "-subj", "/CN=test"],
            check=True, capture_output=True,
        )
        monkeypatch.setenv("NOMAD_ADDR", "https://127.0.0.1:4646")
        monkeypatch.setenv("NOMAD_CACERT", str(crt))
        client = ship.NomadClient()
        assert client.ctx is not None
        assert client.ctx.check_hostname is True


class TestCli:
    def test_deploy_requires_name_or_job(self, capsys):
        with pytest.raises(SystemExit):
            ship.main(["deploy", "--image", "app:v1"])

    def test_unknown_command_rejected(self):
        with pytest.raises(SystemExit):
            ship.main(["frobnicate"])

    def test_build_missing_dockerfile_errors(self, tmp_path, capsys):
        rc = ship.main(["build", str(tmp_path), "--image", "app:v1"])
        assert rc == 1
        assert "no Dockerfile" in capsys.readouterr().err

#!/usr/bin/env python3
import argparse
import os
import subprocess
import jinja2
from dotenv import load_dotenv
import yaml

parser = argparse.ArgumentParser(description="Deploy Neo4j GenAI Stack")
parser.add_argument("--orchestrator", choices=["docker", "podman", "kubernetes"], required=True,
                    help="Deployment orchestrator")
parser.add_argument("--env-file", default=".env", help="Path to .env file")
parser.add_argument("--extra-vars", nargs="*", help="Extra Ansible vars (key=value)")
parser.add_argument("--playbook", default="ansible/deploy.yml", help="Ansible playbook path")
args = parser.parse_args()

load_dotenv(args.env_file)
env_vars = {
    k: os.getenv(k) for k in os.environ
    if k.startswith(('NEO4J_', 'OLLAMA_', 'LLM', 'EMBEDDING_', 'OPENAI_', 'AWS_', 'GOOGLE_', 'LANGCHAIN_'))
}
env_vars["replicas"] = os.getenv("REPLICAS", "1")

template_dir = "templates"
env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))

if args.orchestrator in ["docker", "podman"]:
    template = env.get_template("docker-compose.yml.j2")
    rendered = template.render(**env_vars, orchestrator=args.orchestrator)
    with open("docker-compose.yml", "w") as f:
        f.write(rendered)
    print("Rendered docker-compose.yml")

ansible_cmd = [
    "ansible-playbook", args.playbook,
    "-i", "ansible/hosts.ini",
    "-e", f"orchestrator={args.orchestrator}",
    "-e", f"env_file={args.env_file}",
]
if args.extra_vars:
    ansible_cmd += ["-e", " ".join(args.extra_vars)]
subprocess.run(ansible_cmd, check=True)
print("Deployment completed via Ansible.")
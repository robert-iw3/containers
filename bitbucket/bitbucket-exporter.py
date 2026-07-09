from prometheus_client import start_http_server, Counter, Gauge
import requests
import time
import os

# Prometheus metrics
repo_pushes = Counter('bitbucket_repo_pushes_total', 'Total repository pushes', ['repository'])
repo_pulls = Counter('bitbucket_repo_pulls_total', 'Total repository pulls', ['repository'])
repo_clones = Counter('bitbucket_repo_clones_total', 'Total repository clones', ['repository'])
repo_activity = Gauge('bitbucket_repo_activity_timestamp', 'Last activity timestamp', ['repository'])

def fetch_bitbucket_metrics(bitbucket_url, admin_user, admin_password):
    """Fetch repository activity from Bitbucket REST API."""
    try:
        response = requests.get(f"{bitbucket_url}/rest/api/1.0/projects",
                               auth=(admin_user, admin_password), timeout=5)
        response.raise_for_status()
        projects = response.json()['values']
        for project in projects:
            project_key = project['key']
            repos_response = requests.get(f"{bitbucket_url}/rest/api/1.0/projects/{project_key}/repos",
                                        auth=(admin_user, admin_password), timeout=5)
            repos_response.raise_for_status()
            repos = repos_response.json()['values']
            for repo in repos:
                repo_slug = repo['slug']
                activity_response = requests.get(f"{bitbucket_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/activity",
                                               auth=(admin_user, admin_password), timeout=5)
                if activity_response.status_code == 200:
                    activities = activity_response.json()['values']
                    for activity in activities:
                        if activity['action'] == 'PUSHED':
                            repo_pushes.labels(repository=f"{project_key}/{repo_slug}").inc()
                        elif activity['action'] == 'PULLED':
                            repo_pulls.labels(repository=f"{project_key}/{repo_slug}").inc()
                        elif activity['action'] == 'CLONED':
                            repo_clones.labels(repository=f"{project_key}/{repo_slug}").inc()
                        repo_activity.labels(repository=f"{project_key}/{repo_slug}").set(time.time())
    except requests.RequestException as e:
        print(f"Error fetching Bitbucket metrics: {e}")

if __name__ == '__main__':
    start_http_server(8000)
    bitbucket_url = os.getenv('BITBUCKET_URL', 'http://172.28.0.4:7990')
    admin_user = os.getenv('BITBUCKET_ADMIN_USER', 'admin')
    admin_password = os.getenv('BITBUCKET_ADMIN_PASSWORD', 'admin_password')
    while True:
        fetch_bitbucket_metrics(bitbucket_url, admin_user, admin_password)
        time.sleep(30)
import json
import requests
from threading import Thread
from .spinner import Spinner
from .config import DEEPSEEK_API_URL, DEEPSEEK_API_KEY, SYSTEM_PROMPT
from requests.exceptions import HTTPError, RequestException

class DeepSeekClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

    def query(self, report_text: str, verbose: bool = False) -> dict:
        prompt = f"""Analyze the following threat report and return MITRE ATT&CK technique mappings and extracted IOCs:\n\n{report_text}"""

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        spinner = Spinner("[*] Analyzing with DeepSeek...")
        thread = Thread(target=spinner.start)

        if verbose:
            print("[*] Sending request to DeepSeek API...")

        try:
            thread.start()
            response = requests.post(DEEPSEEK_API_URL, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()

        except HTTPError as http_err:
            if response.status_code == 401:
                raise Exception("[!] Unauthorized: Your DeepSeek API key is missing or invalid.")
            else:
                raise Exception(f"[!] DeepSeek API HTTP error: {http_err}")

        except RequestException as req_err:
            raise Exception(f"[!] DeepSeek API request failed: {req_err}")

        except Exception as e:
            raise Exception(f"[!] Unexpected error during DeepSeek query: {str(e)}")

        finally:
            spinner.stop()

    def generate_title(self, full_text: str, verbose: bool = False) -> str:
        prompt = f"""
    Write a concise threat intelligence report title (maximum 15 words) in English based on the following content.

    The title must reflect:
    - Initial access vector (e.g., exploit, phishing)
    - Key tools or malware (e.g., Cobalt Strike, Mimikatz, ransomware)
    - Final impact (e.g., lateral movement, data encryption)

    Use a professional, CTI-style tone. Do not use quotation marks, markdown, or headings.

    Report content:
    {full_text[:8000]}
    """

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a cybersecurity analyst skilled in writing concise threat report titles."},
                {"role": "user", "content": prompt.strip()}
            ],
            "temperature": 0.3
        }

        spinner = Spinner("[*] Generating report title...")
        thread = Thread(target=spinner.start)

        try:
            thread.start()
            response = requests.post(DEEPSEEK_API_URL, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip() or "Untitled Threat Report"
        except Exception as e:
            if verbose:
                print(f"[!] Title generation failed: {e}")
            return "Untitled Threat Report"
        finally:
            spinner.stop()


    def summarize(self, full_text: str, verbose: bool = False) -> str:
        prompt = f"""
Summarize the following threat report into 1–2 sentences (maximum 1000 characters).
The summary must include:
- Initial access vector (e.g., phishing, RDP, exploit)
- Key tools or malware (e.g., Cobalt Strike, Mimikatz, ransomware)
- Lateral movement or privilege escalation tactics
- Final impact or objective (e.g., data exfiltration, encryption, persistence)

Only return the summary. Do not add any heading or markdown formatting.

Report content:
{full_text[:8000]}
"""

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a cybersecurity analyst experienced in summarizing threat intelligence reports."},
                {"role": "user", "content": prompt.strip()}
            ],
            "temperature": 0.2
        }

        spinner = Spinner("[*] Generating summary...")
        thread = Thread(target=spinner.start)

        if verbose:
            print("[*] Sending summarization request...")

        try:
            thread.start()
            response = requests.post(DEEPSEEK_API_URL, headers=self.headers, json=payload)
            response.raise_for_status()

            content = response.json()['choices'][0]['message']['content']
            summary = content.strip()

            if not summary or len(summary.split()) < 10:
                if verbose:
                    print("[!] Warning: Summary too short or malformed.")
                return "Summary not available or incomplete."
            return summary

        except HTTPError as http_err:
            if response.status_code == 401:
                return "[!] Summary failed: Invalid DeepSeek API key."
            return f"[!] Summary failed with HTTP error: {http_err}"

        except RequestException as req_err:
            return f"[!] Summary failed: Network/API error: {req_err}"

        except Exception as e:
            return f"[!] Summary not available due to unexpected error: {str(e)}"

        finally:
            spinner.stop()

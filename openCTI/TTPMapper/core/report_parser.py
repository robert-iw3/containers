import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from urllib.parse import urlparse
import html2text
import json

class ReportParser:
    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False

    def fetch_and_convert_report(self, url: str, output_format: str = "markdown") -> str:
        """
        Fetch content from a given URL and convert to Markdown or raw text.
        Supports HTML and JSON content types.
        """
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError("Invalid URL format.")

        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')

        if 'application/json' in content_type:
            data = response.json()
            return json.dumps(data, indent=2) if output_format == "json" else self.json_to_markdown(data)

        elif 'text/html' in content_type:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove unwanted tags
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()

            return self.html_converter.handle(str(soup))

        else:
            return response.text  # fallback for text/plain or unknown

    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract raw text from each page of a PDF.
        """
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"[!] Failed to read PDF: {str(e)}")

    def convert_pdf_to_markdown(self, file_path: str) -> str:
        """
        Convert extracted PDF text into Markdown-style structure using basic HTML heuristics.
        """
        raw_text = self.extract_text_from_pdf(file_path)
        html_content = "<html><body>\n"
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.isupper() or line.endswith(":"):
                html_content += f"<h3>{line}</h3>\n"
            else:
                html_content += f"<p>{line}</p>\n"
        html_content += "</body></html>"
        return self.html_converter.handle(html_content)

    def json_to_markdown(self, json_data: dict) -> str:
        """
        Convert nested JSON content into human-readable Markdown format.
        """
        markdown = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if isinstance(value, (dict, list)):
                    markdown.append(f"## {key}\n{self.json_to_markdown(value)}")
                else:
                    markdown.append(f"**{key}**: {value}")
        elif isinstance(json_data, list):
            for item in json_data:
                markdown.append(f"- {self.json_to_markdown(item)}")
        else:
            markdown.append(str(json_data))
        return "\n".join(markdown)

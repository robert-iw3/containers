import sys
import time
import threading
import itertools
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)  # Enable color on Windows too

class Spinner:
    def __init__(self, message="Processing", delay=0.1, success_text="Done!", fail_text="Failed."):
        self.spinner_cycle = itertools.cycle(['|', '/', '-', '\\'])
        self.delay = delay
        self.message = message
        self.success_text = success_text
        self.fail_text = fail_text
        self.running = False
        self.thread = None
        self.start_time = None
        self.status = None  # "success" or "fail"

    def start(self):
        self.running = True
        self.status = None
        self.start_time = datetime.now()
        sys.stdout.write(Fore.CYAN + self.message + " ")
        sys.stdout.flush()
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()

    def _spin(self):
        while self.running:
            sys.stdout.write(next(self.spinner_cycle))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')

    def stop(self, success=True):
        self.running = False
        self.status = "success" if success else "fail"
        if self.thread:
            self.thread.join()
        duration = (datetime.now() - self.start_time).total_seconds()
        result_text = (
            Fore.GREEN + self.success_text if success
            else Fore.RED + self.fail_text
        )
        sys.stdout.write('\b' + result_text + f" ({duration:.2f}s)\n")
        sys.stdout.flush()

from google import genai
from google.genai import types
import time
import os
import sys
import io

os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))


from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))


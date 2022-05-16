#!/usr/bin/env python3
import os
import sys
import re
import json
import time
from signal import signal, SIGINT
import argparse
import traceback

from selenium import webdriver

#from selenium.webdriver.chrome.service import Service
#from webdriver_manager.chrome import ChromeDriverManager
#from selenium.webdriver.chrome.options import Options
#from webdriver_manager.utils import ChromeType

from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

supported_languages = {
	'es': 'es-ES',
	'de': 'de-DE',
	'it': 'it-IT',
	'ru': 'ru-RU',
	'zh': 'zh-ZH',
	'pl': 'pl-PL',
	'sv': 'sv-SV',
}

todoCharCounter = 0
maxRuntime = 0
startTime = time.time()


class Translator:
	def __init__(self, language: str, cacheFile: str, useDeepl: bool, glossary_file: str, recheckWords: list):
		self._language = language

		self._cacheFile = cacheFile
		self._cacheDirty = False
		self._cacheData = {}
		if os.path.exists(cacheFile):
			with(open(cacheFile)) as f:
				self._cacheData = json.load(f)

		self._useDeepl = useDeepl
		self._glossary = {}
		self._deeplGlossary = []
		self._recheckWords = recheckWords

		self.charCount = 0
		self.cachedCharCount = 0
		self._webdriver = None

		if os.path.exists(glossary_file):
			with open(glossary_file) as f:
				self._glossary = json.load(f)

	def __enter__(self):
		signal(SIGINT, self._sigint_handler)
		return self

	def _sigint_handler(self, signal_received, frame):
		self.__exit__(None, None, None)
		sys.exit(0)

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.cacheSync()
		if self._webdriver:
			self._webdriver.quit()

	def cacheSync(self):
		if self._cacheDirty:
			with open(f"{self._cacheFile}.swp", mode='w', encoding='utf-8') as f:
				json.dump(self._cacheData, f, indent='\t', ensure_ascii=False)
			os.rename(f"{self._cacheFile}.swp", self._cacheFile)
			self._cacheDirty = False

	def cacheSet(self, key, value):
		self._cacheData[key] = value
		self._cacheDirty = True

	def cacheDelete(self, key):
		del self._cacheData[key]
		self._cacheDirty = True

	def cacheGet(self, key):
		return self._cacheData[key]

	def initWebdriver(self):
		if self._webdriver is not None:
			self._webdriver.quit()

		#chrome_options = Options()
		#chrome_options.add_argument("--headless")
		#chrome_options.binary_location = '/usr/bin/chromium-freeworld'
		#chrome_options.add_argument("--window-size=1920,1080")
		#self._webdriver = webdriver.Chrome(options=chrome_options, service=Service(ChromeDriverManager(version="100.0.4896.60", chrome_type=ChromeType.CHROMIUM).install()))

		firefox_options = Options()
		firefox_options.add_argument("--headless")
		firefox_options.add_argument("--window-size=1920,1080")
		if 'SOCKS_PROXY' in os.environ:
			proxy_host, proxy_port = os.environ['SOCKS_PROXY'].split(':')
			firefox_options.set_preference('network.proxy.type', 1)
			firefox_options.set_preference('network.proxy.socks', proxy_host)
			firefox_options.set_preference('network.proxy.socks_port', proxy_port)
		self._webdriver = webdriver.Firefox(options=firefox_options, service=Service(GeckoDriverManager().install()))
		self._webdriver.set_window_size(1920, 1080)

		self._webdriver.get("https://www.deepl.com/en/translator")

		# Select from / to languages
		WebDriverWait(self._webdriver, 5).until(EC.presence_of_element_located((By.XPATH, '//button[@dl-test="translator-source-lang-btn"]'))).click()
		# div[@dl-test=translator-source-lang-list]
		WebDriverWait(self._webdriver, 1).until(EC.presence_of_element_located((By.XPATH, '//button[@dl-test="translator-lang-option-en"]'))).click()

		WebDriverWait(self._webdriver, 1).until(EC.presence_of_element_located((By.XPATH, '//button[@dl-test="translator-target-lang-btn"]'))).click()
		# div[@dl-test=translator-target-lang-list]
		WebDriverWait(self._webdriver, 1).until(EC.presence_of_element_located((By.XPATH, f"//button[@dl-test=\"translator-lang-option-{supported_languages[self._language]}\"]"))).click()

		self._inputField = self._webdriver.find_element(By.XPATH, '//textarea[@dl-test="translator-source-input"]')
		self._outputField = self._webdriver.find_element(By.XPATH, '//*[@id="target-dummydiv"]')

		# Init glossary
		self._deeplGlossary = []

	def _setupGlossary(self, text: str):
		contains = {
			word: translation
			for word, translation in self._glossary.items()
			if word.lower() in text.lower() and word not in self._deeplGlossary
		}
		if len(contains) == 0:
			return

		self._webdriver.find_element(By.CLASS_NAME, 'lmt__glossary_button_label').click()
		WebDriverWait(self._webdriver, 1).until(EC.presence_of_element_located((By.XPATH, '//button[@dl-test="glossary-close-editor"]')))

		entries = self._webdriver.find_elements(By.XPATH, '//button[@dl-test="glossary-entry-delete-button"]')
		# Delete some if needed
		for i in range(0, -10+(len(entries)+len(contains))):
			removed_word = entries[i].parent.find_element(By.XPATH, '//span[@dl-test="glossary-entry-source-text"]').text
			print(f"remove '{removed_word}' from glossary to make room")
			entries[i].click()
			self._deeplGlossary.remove(removed_word)

		for word, translation in contains.items():
			print(f"adding {word}:{translation} to glossary")
			self._webdriver.find_element(By.XPATH, '//input[@dl-test="glossary-newentry-source-input"]').send_keys(word)
			self._webdriver.find_element(By.XPATH, '//input[@dl-test="glossary-newentry-target-input"]').send_keys(translation)
			self._webdriver.find_element(By.XPATH, '//button[@dl-test="glossary-newentry-accept-button"]').click()
			time.sleep(0.5)
			self._deeplGlossary.append(word)

		# close
		WebDriverWait(self._webdriver, 1).until(EC.presence_of_element_located((By.XPATH, '//button[@dl-test="glossary-close-editor"]'))).click()


	def _needsRecheck(self, text: str) -> bool:
		for word in self._recheckWords:
			# ignore vars and case
			checkText = re.sub('{.*?}', '', text.lower())
			if word.lower() in checkText:
				return True

		return False

	def links2tags(self, text: str) -> tuple[str, list]:
		# Replace links with specific markers we can put in place after translating later
		links = []
		count = 0
		link = re.search("{.*?}", text)
		while link is not None:
			links.append(link.group(0))
			text = re.sub("{.*?}", f"(%{count}%)", text, 1)
			count += 1
			link = re.search("{.*?}", text)

		return text, links


	def tags2links(self, text: str, links: list) -> str:
		for idx, link in enumerate(links):
			text = re.sub(f"\(%{idx}%\)", link, text)

		return text


	def translate(self, text: str) -> str:
		# Do not translate variable only and very short or non alpha texts
		noVars = re.sub('{.*?}', '', text)
		if len(re.sub('[\d\s()\[\].,_-]+', '', noVars)) < 5:
			return text


		# Serve from cache if present
		if text in self._cacheData:
			if self._needsRecheck(text):
				print(text)
				print(self.cacheGet(text))
				self.cacheDelete(text)
			else:
				translated_text = self.cacheGet(text)
				if translated_text is not None:
					self.cachedCharCount += len(text)
					return translated_text


		global maxRuntime, startTime
		if maxRuntime != 0 and time.time() - startTime > maxRuntime:
			raise Exception('maximum runtime exceeded - aborting')

		self.charCount += len(text)
		if not self._useDeepl:
			return text
		elif self._webdriver is None:
			self.initWebdriver()


		# Replace links with specific markers we can put in place after translating later
		translate_text, links = self.links2tags(text)

		self._setupGlossary(translate_text)

		self._inputField.click()
		self._inputField.clear()
		time.sleep(0.5)
		self._inputField.send_keys(translate_text)

		translator_working = WebDriverWait(self._webdriver, 1).until(EC.presence_of_element_located((By.XPATH, '//main[@id="dl_translator"]')))

		maxwait = 50 # 10s
		translated_text = ""
		while 'lmt--active_translation_request' in translator_working.get_attribute("class"):
			time.sleep(0.2)

			maxwait -= 1
			if maxwait <= 0:
				#self._webdriver.save_screenshot("screenshot_timeout.png")
				translated_text = self._outputField.get_attribute("textContent").rstrip()
				raise Exception(f"Timed out. Translation probably incomplete ({len(translated_text) / len(translate_text)}) '{translate_text}' '{translated_text}'")

		time.sleep(0.5)
		translated_text = self._outputField.get_attribute("textContent").rstrip()

		# Replace back any placeholders for links
		translated_text = self.tags2links(translated_text, links)

		# Click the input to make sure the translation is really complete and we were not blocked
		# This will raise an exception otherwise
		self._inputField.click()

		print(text)
		print(translated_text)
		self.cacheSet(text, translated_text)
		print()

		return translated_text


def translate_data(translator: Translator, data):
	if type(data) is list:
		for element in data:
			translate_data(translator, element)
	elif type(data) is dict:
		for k, v in data.items():
			# We only translate specific keys from dicts
			if k in  ['entry', 'effect'] and type(v) is str:
				data[k] = translator.translate(v)
			elif k == 'other' and type(v) is dict:
				# Special hack for life.json
				for section, items in v.items():
					for idx, item in enumerate(items):
						data[k][section][idx] = translator.translate(item)
			elif k in ['entries', 'items', 'rows', 'headerEntries', 'reasons', 'other', 'lifeTrinket'] and type(v) is list:

				# Do not translate for simple item lists withou type: list (to avoid translating item names)
				if k == "items" and ("type" not in data or data['type'] != 'list'):
					continue

				for idx, entry in enumerate(v):
					if type(entry) is list:
						for elidx, el in enumerate(entry):
							if type(el) is str and len(el) > 2:
								data[k][idx][elidx] = translator.translate(el)

					if type(entry) is str:
						data[k][idx] = translator.translate(entry)
					else:
						translate_data(translator, entry)
			else:
				translate_data(translator, v)

def translate_file(language: str, fileName: str, writeJSON: bool, useDeepl: bool, recheckWords: list):
	cache_file = fileName.replace("data/", f"translation/cache/{language}/")
	os.makedirs(os.path.dirname(cache_file), exist_ok=True)

	glossary_file = f"translation/glossary/{language}.json"
	os.makedirs(os.path.dirname(glossary_file), exist_ok=True)

	output_file = fileName.replace("data/", f"data.{language}/")
	os.makedirs(os.path.dirname(output_file), exist_ok=True)

	data = {}
	with Translator(language, cache_file, useDeepl, glossary_file, recheckWords) as translator:
		print(f"Translating\t{file}")
		try:
			with open(fileName) as f:
				data = json.load(f)
			translate_data(translator, data)
		except Exception as e:
			print(repr(e))
			traceback.print_exc()
			# Make sure we save what we got
			translator.cacheSync()

		print(f"Cached:{translator.cachedCharCount}\tTodo: {translator.charCount}")
		global todoCharCounter
		todoCharCounter += translator.charCount

	if writeJSON:
		with open(output_file, 'w', encoding='utf-8') as f:
			json.dump(data, f, indent='\t', ensure_ascii=False)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Translate json data')
	parser.add_argument('--language', type=str, required=True)
	parser.add_argument('--translate', type=bool, default=False, action=argparse.BooleanOptionalAction)
	parser.add_argument('--deepl', type=bool, default=False, action=argparse.BooleanOptionalAction)
	parser.add_argument('--maxrun', type=int, default=False)
	parser.add_argument('--recheck-words', type=str, default=[], nargs='*')
	parser.add_argument('files', type=str, nargs='*')
	args = parser.parse_args()
	maxRuntime = args.maxrun

	if args.language.lower() not in supported_languages:
		raise Exception(f"Unsupported language {args.language} - Valid are: {supported_languages.keys()}")

	for file in args.files:
		if file.startswith("data/generated"):
			continue

		translate_file(args.language.lower(), file, args.translate, args.deepl, args.recheck_words)

	print(f"Total todo: {todoCharCounter}")

#!/usr/bin/env python3
import os
import sys
import re
import json
import time
from signal import signal, SIGINT
from sys import platform
import argparse
import traceback

from selenium import webdriver
from selenium.webdriver.common.keys import Keys

# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.utils import ChromeType

from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.common.action_chains import ActionChains

from metric_converter import convertToMetric

supported_languages = {
    "es": "es-ES",
    "de": "de-DE",
    "it": "it-IT",
    "ru": "ru-RU",
    "zh": "zh-ZH",
    "pl": "pl-PL",
    "sv": "sv-SV",
    "fr": "fr-FR",
    "nl": "nl-NL",
}

todoCharCounter = 0
maxRuntime = 0
startTime = time.time()


class Translator:
    def __init__(
        self,
        language: str,
        cacheFile: str,
        useDeepl: bool,
        glossary_folder: str,
        recheckWords: list,
        retranslateGlossaryModified: bool,
        retranslateGlossaryForce: bool,
        convertToMetricSystem: bool,
    ):
        self._language = language

        # self._tag_regex = '{(?!(@i )|(@italic )|(@b )|(@bold )|(@u )|(@underline )|(@s )|(@strike )|(@color )|(@note )|(@footnote )).*?}'
        # self._tag_regex = '{(?!(@note )|(@footnote )).*?}'
        self._tag_regex = "{.*?}"

        self._cacheFile = cacheFile
        self._cacheDirty = False
        self._cacheData = {}
        if os.path.exists(cacheFile):
            with open(cacheFile) as f:
                self._cacheData = json.load(f)

        self._useDeepl = useDeepl
        self._glossary = {}
        self._deeplGlossary = []
        self._recheckWords = recheckWords
        self._convertToMetricSystem = convertToMetricSystem

        self.charCount = 0
        self.cachedCharCount = 0
        self._webdriver = None

        # We load both our glossary and the entities translations cache
        # The glossary has priority
        self._glossary = self.loadGlossary()
        self._entitiesCacheData = self.loadEntitiesCache()
        self._entitiesNameDirty = False

        (
            new_glossary_keys,
            modified_glossary_keys,
            deleted_glossary_key,
        ) = self.glossaryDiff()
        if retranslateGlossaryForce:
            print("Retranslating all string that contain a glossary word")
            self._recheckWords = list(
                set(self._recheckWords + [key.lower() for key in self._glossary.keys()])
            )
        elif retranslateGlossaryModified:
            print(
                "Retranslating strings that contains words for which there is a new or modified glossary translation"
            )
            self._recheckWords = list(
                set(self._recheckWords + new_glossary_keys + modified_glossary_keys)
            )

        # We remove from the entities translations the ones that came from the glossary and are no longer in it
        for k in deleted_glossary_key:
            if k in self._entitiesCacheData:
                print(f"Deleting {k} from entities cache")
                self.entitiesCacheDelete(k)

        # We then add the entities to the glossary for this run
        self._glossary = self._entitiesCacheData | self._glossary

    def __enter__(self):
        signal(SIGINT, self._sigint_handler)
        return self

    def _sigint_handler(self, signal_received, frame):
        self.__exit__(None, None, None)
        sys.exit(0)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cacheSync()
        self.entitiesCacheSync()
        if self._webdriver:
            self._webdriver.quit()

    def cacheSync(self):
        if self._cacheDirty:
            with open(f"{self._cacheFile}.swp", mode="w", encoding="utf-8") as f:
                json.dump(self._cacheData, f, indent="\t", ensure_ascii=False)
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

        # chrome_options = Options()
        # chrome_options.add_argument("--headless")
        # chrome_options.binary_location = '/usr/bin/chromium-freeworld'
        # chrome_options.add_argument("--window-size=1920,1080")
        # self._webdriver = webdriver.Chrome(options=chrome_options, service=Service(ChromeDriverManager(version="100.0.4896.60", chrome_type=ChromeType.CHROMIUM).install()))

        firefox_options = Options()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--window-size=1920,1080")
        if "SOCKS_PROXY" in os.environ:
            proxy_host, proxy_port = os.environ["SOCKS_PROXY"].split(":")
            firefox_options.set_preference("network.proxy.type", 1)
            firefox_options.set_preference("network.proxy.socks", proxy_host)
            firefox_options.set_preference("network.proxy.socks_port", proxy_port)
        # self._webdriver = webdriver.Firefox(options=firefox_options, service=Service(GeckoDriverManager().install()))
        self._webdriver = webdriver.Firefox(options=firefox_options)
        self._webdriver.set_window_size(1920, 1080)

        self._webdriver.get(f"https://www.deepl.com/en/translator#en/{self._language}/")

        self._inputField = self._webdriver.find_element(
            By.XPATH, '//*[@data-testid="translator-source-input"]'
        )
        self._outputField = self._webdriver.find_element(
            By.XPATH, '//*[@data-testid="translator-target-input"]'
        )

        # Init glossary
        self._deeplGlossary = []

    def _setupGlossary(self, text: str):
        # We sort the glossary to have the longuest words first. That way "Orc Chieftain" we be added before "Orc"
        sorted_glossary = {}
        for k in sorted(self._glossary, key=len, reverse=True):
            sorted_glossary[k] = self._glossary[k]

        contains = {}
        # We avoid adding the translation with caps if the word is lowercase in the text.
        # To avoid common words like 'alarm', which is also a spell to always be capitalised.
        for word, translation in sorted_glossary.items():
            if (
                re.match(r".*\b" + re.escape(word) + r"\b.*", text)
                and word not in self._deeplGlossary
            ):
                contains[word] = translation
            elif (
                re.match(r".*\b" + re.escape(word.lower()) + r"\b.*", text.lower())
                and word not in self._deeplGlossary
            ):
                contains[word.lower()] = translation.lower()

        if len(contains) == 0:
            return

        self._webdriver.find_element(
            By.CLASS_NAME, "lmt__glossary_button_label"
        ).click()
        WebDriverWait(self._webdriver, 1).until(
            EC.presence_of_element_located(
                (By.XPATH, '//button[@data-testid="glossary-close-editor"]')
            )
        )

        entries = self._webdriver.find_elements(
            By.XPATH, '//button[@data-testid="glossary-entry-delete-button"]'
        )
        # Delete some if needed
        for i in range(0, -10 + (len(entries) + len(contains))):
            removed_word = (
                entries[i]
                .parent.find_element(
                    By.XPATH,
                    '//span[@data-testid="glossary-entry-source-text"]',
                )
                .text
            )
            print(f"remove '{removed_word}' from glossary to make room")
            entries[i].click()
            try:
                self._deeplGlossary.remove(removed_word)
            except:
                # In some case the removal from Deepl fails but it's already removed from out list
                pass

        for word, translation in contains.items():
            print(f"adding {word}:{translation} to glossary")
            try:
                self._webdriver.find_element(
                    By.XPATH,
                    '//input[@data-testid="glossary-newentry-source-input"]',
                ).send_keys(word)
                self._webdriver.find_element(
                    By.XPATH,
                    '//input[@data-testid="glossary-newentry-target-input"]',
                ).send_keys(translation)
                self._webdriver.find_element(
                    By.XPATH,
                    '//button[@data-testid="glossary-newentry-accept-button"]',
                ).click()
            except:
                self._webdriver.find_element(
                    By.XPATH,
                    '//input[@data-testid="glossary-newentry-source-input"]',
                ).send_keys(word)
                self._webdriver.find_element(
                    By.XPATH,
                    '//input[@data-testid="glossary-newentry-target-input"]',
                ).send_keys(translation)
                self._webdriver.find_element(
                    By.XPATH,
                    '//button[@data-testid="glossary-newentry-accept-button"]',
                ).click()
            time.sleep(0.5)
            self._deeplGlossary.append(word)

        # close
        WebDriverWait(self._webdriver, 1).until(
            EC.presence_of_element_located(
                (By.XPATH, '//button[@data-testid="glossary-close-editor"]')
            )
        ).click()

    def _needsRecheck(self, text: str) -> bool:
        for word in self._recheckWords:
            # ignore vars and case
            checkText = re.sub(self._tag_regex, "", text.lower())
            if re.match(r"(?i).*\b" + re.escape(word) + r"\b.*", checkText):
                return True

        return False

    def links2tags(self, text: str) -> tuple[str, list]:
        # Replace links with specific markers we can put in place after translating later
        links = []
        count = 0
        link = re.search("{.*?}", text)
        while link is not None:
            links.append(link.group(0))
            text = re.sub(self._tag_regex, f"(%{count}%)", text, 1)
            count += 1
            link = re.search(self._tag_regex, text)

        return text, links

    def tags2links(self, text: str, links: list) -> str:
        for idx, link in enumerate(links):
            match = re.match(r"{@([a-z]*)\s+([A-Za-z ]*?)(\|.*)?}", link)
            if match:
                # Tags are only translated using glossary and entity names.
                translated_tag = self.translateTag(match.group(2))
                link = f"{{@{match.group(1)} {translated_tag}{match.group(3) or ''}}}"
                print(link)

            text = re.sub(f"\(%{idx}%\)", link, text)

        return text

    # Returns the glossary to use
    def loadGlossary(self):
        glossary_folder = f"translation/glossary/{self._language}"
        glossary = {}
        os.makedirs(os.path.dirname(glossary_folder), exist_ok=True)
        if os.path.exists(glossary_folder):
            for file in os.listdir(glossary_folder):
                file_path = os.path.join(glossary_folder, file)
                if os.path.isfile(file_path) and file_path.endswith(".json"):
                    with open(file_path) as f:
                        glossary = json.load(f) | glossary
        # We lowercase the key to avoid some odd capital
        return glossary

    def glossaryCachePath(self):
        cache_file = self._cacheFile.replace("translation/cache/", "")
        return f"translation/cache/{self._language}/glossary/{cache_file}"

    # Return the glossary lastly used for a specific file
    def glossaryCacheGet(self):
        glossary_cache_path = self.glossaryCachePath()
        if os.path.exists(glossary_cache_path):
            with open(glossary_cache_path) as f:
                return json.load(f)
        return {}

    def glossaryCacheSave(self):
        glossary_cache_path = self.glossaryCachePath()
        os.makedirs(os.path.dirname(glossary_cache_path), exist_ok=True)

        with open(glossary_cache_path, mode="w", encoding="utf-8") as f:
            json.dump(self._glossary, f, indent="\t", ensure_ascii=False)

    # Returns new words in glossary, words for which the translation as changed and words that have been removed from the glossary
    def glossaryDiff(self):
        cached_glossary = self.glossaryCacheGet()
        new_glossary = self._glossary
        modified_keys = []
        new_keys = []
        deleted_keys = []
        for key in new_glossary:
            if key not in cached_glossary:
                print(f"{key} was added from previously used glossary")
                new_keys.append(key.lower())
            elif cached_glossary[key] != new_glossary[key]:
                print(f"{key} was modified from previously used glossary")
                modified_keys.append(key.lower())
        for key in cached_glossary:
            if key not in new_glossary:
                print(f"{key} was removed from previously used glossary")
                deleted_keys.append(key.lower())
        return new_keys, modified_keys, deleted_keys

    # Entities names are translations for the entities (spells, monsters) that we should only translate once for the whole files
    def entitiesNamesCachePath(self):
        return f"translation/cache/{self._language}/glossary/entities_names.json"

    def loadEntitiesCache(self):
        path = self.entitiesNamesCachePath()
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {}

    def entitiesCacheSet(self, key: str, value: str):
        self._entitiesCacheData[key] = value
        self._entitiesNameDirty = True

    def entitiesCacheDelete(self, key: str):
        del self._entitiesCacheData[key]
        self._entitiesNameDirty = True

    def entitiesCacheSync(self):
        if self._entitiesNameDirty:
            path = self.entitiesNamesCachePath()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, mode="w", encoding="utf-8") as f:
                json.dump(self._entitiesCacheData, f, indent="\t", ensure_ascii=False)

    def translateTag(self, tag):
        for k, v in self._glossary.items():
            if tag.lower() == k.lower():
                return v
        return tag

    def translate(self, text: str, isEntityName: bool = False) -> str:
        # Do not translate variable only and very short or non alpha texts
        noVars = re.sub(self._tag_regex, "", text)
        if len(re.sub("[\d\s()\[\].,_-]+", "", noVars)) < 3:
            return text

        # Convert to metric system
        if self._convertToMetricSystem:
            text = convertToMetric(text)

        # Serve from cache if present
        if text in self._cacheData and len(self.cacheGet(text)) > 0:
            if self._needsRecheck(text):
                print("Needs recheck")
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
            raise Exception("maximum runtime exceeded - aborting")

        self.charCount += len(text)
        if not self._useDeepl:
            return text
        elif self._webdriver is None:
            self.initWebdriver()

        # Replace links with specific markers we can put in place after translating later
        translate_text, links = self.links2tags(text)

        self._setupGlossary(translate_text)

        self._inputField.click()
        actions = ActionChains(self._webdriver)
        if platform == "darwin":
            actions.key_down(Keys.COMMAND).send_keys('A').key_up(Keys. COMMAND).send_keys(Keys.BACKSPACE)
        else:
            actions.key_down(Keys.CONTROL).send_keys('A').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE)
        actions.perform()

        time.sleep(0.5)
        actions.send_keys(translate_text)
        actions.perform()

        translator_working = WebDriverWait(self._webdriver, 1).until(
            EC.presence_of_element_located((By.XPATH, '//main[@id="dl_translator"]'))
        )

        maxwait = 50  # 10s
        translated_text = ""
        while "lmt--active_translation_request" in translator_working.get_attribute(
            "class"
        ):
            time.sleep(0.2)

            maxwait -= 1
            if maxwait <= 0:
                # self._webdriver.save_screenshot("screenshot_timeout.png")
                translated_text = self._outputField.get_attribute(
                    "textContent"
                ).rstrip()
                raise Exception(
                    f"Timed out. Translation probably incomplete ({len(translated_text) / len(translate_text)}) '{translate_text}' '{translated_text}'"
                )

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

        # We translated an entity name, save it to the shared cache
        if isEntityName:
            self.entitiesCacheSet(text, translated_text)

        return translated_text


def translate_data(translator: Translator, data):
    if type(data) is list:
        for element in data:
            translate_data(translator, element)
    elif type(data) is dict:
        for k, v in data.items():
            # We only translate specific keys from dicts
            if k in ["entry", "effect", "text", "m"] and type(v) is str:
                data[k] = translator.translate(v)
            elif k == "name" and type(v) is str:
                data[k] = translator.translate(v, isEntityName=True)
            elif k == "other" and type(v) is dict:
                # Special hack for life.json
                for section, items in v.items():
                    for idx, item in enumerate(items):
                        data[k][section][idx] = translator.translate(item)
            elif (
                k
                in [
                    "entries",
                    "items",
                    "rows",
                    "headerEntries",
                    "reasons",
                    "other",
                    "lifeTrinket",
                ]
                and type(v) is list
            ):
                # Do not translate for simple item lists withou type: list (to avoid translating item names)
                if k == "items" and ("type" not in data or data["type"] != "list"):
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


def translate_file(
    language: str,
    fileName: str,
    writeJSON: bool,
    useDeepl: bool,
    recheckWords: list,
    retranslateGlossaryModified: bool,
    retranslateGlossaryForce: bool,
    convertToMetricSystem: bool,
):
    cache_file = fileName.replace("data/", f"translation/cache/{language}/")
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)

    glossary_folder = f"translation/glossary/{language}"
    os.makedirs(os.path.dirname(glossary_folder), exist_ok=True)

    output_file = fileName.replace("data/", f"data.{language}/")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    data = {}
    with Translator(
        language,
        cache_file,
        useDeepl,
        glossary_folder,
        recheckWords,
        retranslateGlossaryModified,
        retranslateGlossaryForce,
        convertToMetricSystem,
    ) as translator:
        print(f"Translating\t{file}")
        try:
            with open(fileName) as f:
                data = json.load(f)
            translate_data(translator, data)
            # Save the used glossary only if everything in the file was translated.
            translator.glossaryCacheSave()
        except Exception as e:
            print(repr(e))
            traceback.print_exc()
            # Make sure we save what we got
            translator.cacheSync()
            translator.entitiesCacheSync()

        print(f"Cached:{translator.cachedCharCount}\tTodo: {translator.charCount}")
        global todoCharCounter
        todoCharCounter += translator.charCount

    if writeJSON:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent="\t", ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate json data")
    parser.add_argument("--language", type=str, required=True)
    parser.add_argument(
        "--translate",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--deepl",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("--maxrun", type=int, default=False)
    parser.add_argument("--recheck-words", type=str, default=[], nargs="*")
    parser.add_argument(
        "--retranslate-glossary-modified",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--retranslate-glossary-force",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--convert-to-metric-system",
        type=bool,
        default=False,
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument("files", type=str, nargs="*")
    args = parser.parse_args()
    maxRuntime = args.maxrun

    if args.language.lower() not in supported_languages:
        raise Exception(
            f"Unsupported language {args.language} - Valid are: {supported_languages.keys()}"
        )

    for file in args.files:
        if file.startswith("data/generated"):
            continue

        translate_file(
            args.language.lower(),
            file,
            args.translate,
            args.deepl,
            args.recheck_words,
            args.retranslate_glossary_modified,
            args.retranslate_glossary_force,
            args.convert_to_metric_system,
        )

    print(f"Total todo: {todoCharCounter}")

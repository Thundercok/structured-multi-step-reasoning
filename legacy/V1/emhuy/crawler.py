import sys
import os
import sqlite3
import logging
import json
import queue
import time
from typing import List, Dict
import requests
from urllib.parse import urljoin, urlparse
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QLineEdit,
    QCheckBox,
    QSpinBox,
    QGroupBox,
    QHBoxLayout,
    QProgressBar,
    QFileDialog,
)
from PyQt6.QtCore import QThread, pyqtSignal
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from shutil import which  # Add this import to detect Chrome binary
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DB_FILE = "crawler_results.db"
DEFAULT_OUTPUT_FOLDER = "output"
DEFAULT_SLEEP_TIME = 2
HASH_MODULO = 10**8

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    title TEXT
)""")
conn.commit()


class Spider(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(
        self,
        start_url: str,
        max_depth: int = 3,
        extract_links: bool = True,
        extract_images: bool = True,
        extract_text: bool = True,
        extract_metadata: bool = True,
        save_html: bool = True,
        output_folder: str = DEFAULT_OUTPUT_FOLDER,
        browser_type: str = "chrome",  # Add browser_type parameter
    ):
        super().__init__()
        self.start_url = start_url
        self.max_depth = max_depth
        self.extract_links = extract_links
        self.extract_images = extract_images
        self.extract_text = extract_text
        self.extract_metadata = extract_metadata
        self.save_html = save_html
        self.output_folder = output_folder
        self.browser_type = browser_type  # Store browser type
        self.visited_urls = set()
        self.url_queue = queue.Queue()
        self.url_queue.put((start_url, 0))
        self.stop_flag = False

    def stop(self) -> None:
        """
        Stops the crawling process.
        """
        self.stop_flag = True

    def run(self) -> None:
        """
        Starts the crawling process.
        """
        os.makedirs(self.output_folder, exist_ok=True)
        self._crawl()

    def _crawl(self) -> None:
        """
        Crawls the web pages starting from the initial URL.
        """
        driver = None

        if self.browser_type == "chrome":
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")

            # Detect Chrome or Brave binary path
            chrome_path = (
                which("google-chrome")
                or which("chrome")
                or which("brave-browser")
            )
            if chrome_path:
                options.binary_location = chrome_path
            else:
                logging.error(
                    "Chrome/Brave binary not found. Please install Google Chrome or Brave. "
                    "Ensure the browser is added to your system's PATH or specify its location manually."
                )
                self.finished.emit(
                    "❌ Chrome/Brave binary not found. Please install Google Chrome or Brave. "
                    "Ensure the browser is added to your system's PATH or specify its location manually."
                )
                return

            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options,
            )

        elif self.browser_type == "firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")
            driver = webdriver.Firefox(
                service=FirefoxService(), options=options
            )

        else:
            logging.error(f"Unsupported browser type: {self.browser_type}")
            self.finished.emit(
                f"❌ Unsupported browser type: {self.browser_type}"
            )
            return

        while not self.url_queue.empty() and not self.stop_flag:
            url, depth = self.url_queue.get()
            if depth > self.max_depth or url in self.visited_urls:
                continue

            self.visited_urls.add(url)
            try:
                driver.get(url)
                time.sleep(DEFAULT_SLEEP_TIME)
                title = driver.title.strip() or "Untitled Page"
                url_folder = self._create_output_folder(url)

                links = (
                    self._extract_links(driver) if self.extract_links else []
                )
                images = (
                    self._extract_images(driver) if self.extract_images else []
                )
                text = self._extract_text(driver) if self.extract_text else ""
                metadata = (
                    self._extract_metadata(driver)
                    if self.extract_metadata
                    else {}
                )
                raw_html = driver.page_source if self.save_html else ""

                self._save_crawled_data(
                    url_folder,
                    title,
                    links,
                    images,
                    text,
                    metadata,
                    raw_html,
                    url,
                )
                self._save_to_database(url, title)

                for link in links:
                    absolute_link = urljoin(url, link)
                    if absolute_link not in self.visited_urls:
                        self.url_queue.put((absolute_link, depth + 1))

            except Exception as e:
                logging.error(f"Error while processing {url}: {e}")
                self.finished.emit(f"❌ Error: {e}")

        driver.quit()

    def _create_output_folder(self, url: str) -> str:
        """
        Creates an organized folder structure for the given URL.

        Args:
            url (str): The URL being crawled.

        Returns:
            str: The path to the created folder.
        """
        domain = urlparse(url).netloc.replace(".", "_")
        safe_hash = str(abs(hash(url)) % HASH_MODULO)
        folder_path = os.path.join(self.output_folder, domain, safe_hash)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def _extract_links(self, driver: webdriver.Chrome) -> List[str]:
        """
        Extracts all links from the current page.

        Args:
            driver (webdriver.Chrome): The Selenium WebDriver instance.

        Returns:
            List[str]: A list of extracted links.
        """
        return [
            a.get_attribute("href")
            for a in driver.find_elements(By.TAG_NAME, "a")
            if a.get_attribute("href")
        ]

    def _extract_images(self, driver: webdriver.Chrome) -> List[str]:
        """
        Extracts all image URLs from the current page.

        Args:
            driver (webdriver.Chrome): The Selenium WebDriver instance.

        Returns:
            List[str]: A list of extracted image URLs.
        """
        return [
            img.get_attribute("src")
            for img in driver.find_elements(By.TAG_NAME, "img")
            if img.get_attribute("src")
        ]

    def _extract_text(self, driver: webdriver.Chrome) -> str:
        """
        Extracts all text content from the current page.

        Args:
            driver (webdriver.Chrome): The Selenium WebDriver instance.

        Returns:
            str: The extracted text content.
        """
        return driver.find_element(By.TAG_NAME, "body").text.strip()

    def _extract_metadata(self, driver: webdriver.Chrome) -> Dict[str, str]:
        """
        Extracts metadata from the current page.

        Args:
            driver (webdriver.Chrome): The Selenium WebDriver instance.

        Returns:
            Dict[str, str]: A dictionary of metadata.
        """
        return {
            meta.get_attribute("name"): meta.get_attribute("content")
            for meta in driver.find_elements(By.TAG_NAME, "meta")
            if meta.get_attribute("name")
        }

    def _save_crawled_data(
        self,
        folder: str,
        title: str,
        links: List[str],
        images: List[str],
        text: str,
        metadata: Dict[str, str],
        raw_html: str,
        url: str,
    ) -> None:
        """
        Saves the crawled data to files.

        Args:
            folder (str): The folder to save the data.
            title (str): The page title.
            links (List[str]): The extracted links.
            images (List[str]): The extracted image URLs.
            text (str): The extracted text content.
            metadata (Dict[str, str]): The extracted metadata.
            raw_html (str): The raw HTML content.
            url (str): The URL being crawled.
        """
        self._save_to_file(folder, "title.txt", title)
        self._save_to_file(folder, "links.txt", "\n".join(links))
        self._save_to_file(folder, "text.txt", text)
        self._save_to_json(folder, "metadata.json", metadata)
        if self.save_html:
            self._save_to_file(folder, "source.html", raw_html)
        self._save_to_file(
            folder,
            "crawl_log.txt",
            f"URL: {url}\nTitle: {title}\nExtracted {len(links)} links, {len(images)} images.\n",
        )
        downloaded_images = self._download_images(images, folder)
        self._save_to_file(folder, "images.txt", "\n".join(downloaded_images))

    def _save_to_file(self, folder: str, filename: str, data: str) -> None:
        """
        Saves data to a file.

        Args:
            folder (str): The folder to save the file.
            filename (str): The name of the file.
            data (str): The data to save.
        """
        if data:
            with open(
                os.path.join(folder, filename), "w", encoding="utf-8"
            ) as f:
                f.write(data)

    def _save_to_json(self, folder: str, filename: str, data: Dict) -> None:
        """
        Saves data to a JSON file.

        Args:
            folder (str): The folder to save the file.
            filename (str): The name of the file.
            data (Dict): The data to save.
        """
        if data:
            with open(
                os.path.join(folder, filename), "w", encoding="utf-8"
            ) as f:
                json.dump(data, f, indent=4)

    def _download_images(self, image_urls: List[str], folder: str) -> List[str]:
        """
        Downloads images from the given URLs.

        Args:
            image_urls (List[str]): A list of image URLs.
            folder (str): The folder to save the images.

        Returns:
            List[str]: A list of downloaded image filenames.
        """
        img_folder = os.path.join(folder, "images")
        os.makedirs(img_folder, exist_ok=True)
        downloaded = []
        for img_url in image_urls:
            try:
                response = requests.get(img_url, timeout=5)
                if response.status_code == 200:
                    base_name = (
                        os.path.basename(urlparse(img_url).path)
                        or f"image_{len(downloaded) + 1}.jpg"
                    )
                    img_path = os.path.join(img_folder, base_name)
                    with open(img_path, "wb") as f:
                        f.write(response.content)
                    downloaded.append(base_name)
            except Exception as e:
                logging.error(f"Failed to download image {img_url}: {e}")
                self.finished.emit(f"❌ Image download error: {e}")
        return downloaded

    def _save_to_database(self, url: str, title: str) -> None:
        """
        Saves the crawled data to the database.

        Args:
            url (str): The URL being crawled.
            title (str): The page title.
        """
        cursor.execute(
            "INSERT OR REPLACE INTO results (url, title) VALUES (?, ?)",
            (url, title),
        )
        conn.commit()


class CrawlerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self) -> None:
        """
        Initializes the UI components.
        """
        layout = QVBoxLayout()

        self.title_label = QLabel(
            "<h2>🌍 Huynh Nhat Huy's Awesome Web Crawler</h2>"
        )
        layout.addWidget(self.title_label)

        self.url_label = QLabel("🔗 Enter URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://books.toscrape.com")
        self.url_input.setText("http://books.toscrape.com")
        self.url_input.returnPressed.connect(self.run_spider)
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)

        settings_box = QGroupBox("📊 Extraction Settings")
        settings_layout = QHBoxLayout()
        self.extract_links = QCheckBox("Links", checked=True)
        self.extract_images = QCheckBox("Images", checked=True)
        self.extract_text = QCheckBox("Text", checked=True)
        self.extract_metadata = QCheckBox("Metadata", checked=True)
        self.save_html = QCheckBox("HTML", checked=True)
        settings_layout.addWidget(self.extract_links)
        settings_layout.addWidget(self.extract_images)
        settings_layout.addWidget(self.extract_text)
        settings_layout.addWidget(self.extract_metadata)
        settings_layout.addWidget(self.save_html)
        settings_box.setLayout(settings_layout)
        layout.addWidget(settings_box)

        self.depth_label = QLabel("📏 Max Depth:")
        self.depth_input = QSpinBox(minimum=1, maximum=10, value=3)
        layout.addWidget(self.depth_label)
        layout.addWidget(self.depth_input)

        browser_box = QGroupBox("🌐 Browser Selection")
        browser_layout = QHBoxLayout()
        self.browser_chrome = QCheckBox("Chrome/Brave", checked=True)
        self.browser_firefox = QCheckBox("Firefox")
        self.browser_chrome.toggled.connect(self.toggle_browser_selection)
        self.browser_firefox.toggled.connect(self.toggle_browser_selection)
        browser_layout.addWidget(self.browser_chrome)
        browser_layout.addWidget(self.browser_firefox)
        browser_box.setLayout(browser_layout)
        layout.addWidget(browser_box)

        self.folder_button = QPushButton("📂 Select Output Folder")
        self.folder_button.clicked.connect(self.select_output_folder)
        layout.addWidget(self.folder_button)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_spider = QPushButton("🚀 Crawl!")
        self.btn_spider.clicked.connect(self.run_spider)
        self.btn_stop = QPushButton("⛔ Stop Crawling")
        self.btn_stop.clicked.connect(self.stop_spider)
        btn_layout.addWidget(self.btn_spider)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        self.output = QTextEdit(readOnly=True)
        layout.addWidget(self.output)

        self.setLayout(layout)
        self.setWindowTitle("Huynh Nhat Huy's Awesome Web Crawler")
        self.output_folder = DEFAULT_OUTPUT_FOLDER

    def select_output_folder(self) -> None:
        """
        Opens a dialog to select the output folder.
        """
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output.append(f"Output folder set to: {folder}")

    def toggle_browser_selection(self) -> None:
        """
        Ensures only one browser is selected at a time.
        """
        if self.browser_chrome.isChecked():
            self.browser_firefox.setChecked(False)
        elif self.browser_firefox.isChecked():
            self.browser_chrome.setChecked(False)

    def run_spider(self) -> None:
        """
        Starts the spider with the given settings.
        """
        url = self.url_input.text()
        if url:
            self.status_label.setText("Status: Now Running...")
            browser_type = (
                "chrome" if self.browser_chrome.isChecked() else "firefox"
            )
            self.worker = Spider(
                url,
                max_depth=self.depth_input.value(),
                extract_links=self.extract_links.isChecked(),
                extract_images=self.extract_images.isChecked(),
                extract_text=self.extract_text.isChecked(),
                extract_metadata=self.extract_metadata.isChecked(),
                save_html=self.save_html.isChecked(),
                output_folder=self.output_folder,
                browser_type=browser_type,  # Pass browser type
            )
            self.worker.progress.connect(self.progress_bar.setValue)
            self.worker.finished.connect(self.display_output)
            self.worker.start()

    def stop_spider(self) -> None:
        """
        Stops the spider if it is running.
        """
        if hasattr(self, "worker"):
            self.worker.stop()
            self.status_label.setText("Status: Stopped")
            self.output.append("🛑 Crawling Stopped.")

    def display_output(self, text: str) -> None:
        """
        Displays the output from the spider.

        Args:
            text (str): The text to display.
        """
        self.output.append(text)
        if "✅ Crawled:" in text or "❌" in text:
            self.status_label.setText("Status: Idle")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = CrawlerApp()
    ex.show()
    sys.exit(app.exec())

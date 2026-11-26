#!/usr/bin/env python3
import argparse
import urllib.request
import urllib.error
import os
import sys
import socket
from urllib.parse import urlparse
import time
import logging
from http.cookiejar import CookieJar, MozillaCookieJar

class WgetSSL:
    def __init__(self):
        self.version = "1.0.0"
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.timeout = 30
        self.retry_count = 3
        self.retry_wait = 5

    def setup_logging(self, verbose=False):
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            format='%(levelname)s: %(message)s',
            level=level
        )
        self.logger = logging.getLogger('wget-ssl')

    def parse_args(self):
        parser = argparse.ArgumentParser(
            description='wget-ssl - retrieve files over HTTPS',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        parser.add_argument('url', help='URL to download')
        parser.add_argument('-O', '--output-document',
                          help='Write documents to FILE')
        parser.add_argument('-q', '--quiet', action='store_true',
                          help='Quiet mode - minimal output')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Verbose output')
        parser.add_argument('--timeout', type=int, default=30,
                          help='Set the network timeout in seconds')
        parser.add_argument('--load-cookies', metavar='FILE',
                          help='Load cookies from FILE')
        parser.add_argument('--save-cookies', metavar='FILE',
                          help='Save cookies to FILE')

        return parser.parse_args()

    def get_filename_from_url(self, url):
        """Extract filename from URL or generate a default one"""
        path = urlparse(url).path
        if path:
            return os.path.basename(path) or 'index.html'
        return 'index.html'

    def load_cookies_from_file(self, cookie_file):
        """Load cookies from a Mozilla/Netscape format cookie file"""
        if cookie_file:
            try:
                cookie_jar = MozillaCookieJar(cookie_file)
                cookie_jar.load()
                self.cookie_jar = cookie_jar
                self.opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(self.cookie_jar)
                )
                self.logger.debug(f'Loaded cookies from {cookie_file}')
            except Exception as e:
                self.logger.error(f'Error loading cookies: {e}')

    def save_cookies_to_file(self, cookie_file):
        """Save cookies to a Mozilla/Netscape format cookie file"""
        if cookie_file and isinstance(self.cookie_jar, MozillaCookieJar):
            try:
                self.cookie_jar.save(cookie_file)
                self.logger.debug(f'Saved cookies to {cookie_file}')
            except Exception as e:
                self.logger.error(f'Error saving cookies: {e}')

    def download_file(self, url, output_file):
        retry_count = 0
        while retry_count < self.retry_count:
            try:
                request = urllib.request.Request(url)
                with self.opener.open(request, timeout=self.timeout) as response:
                    total_size = response.getheader('Content-Length')
                    total_size = int(total_size) if total_size else None

                    downloaded = 0
                    with open(output_file, 'wb') as f:
                        while True:
                            chunk = response.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            self._print_progress(downloaded, total_size)

                self.logger.info('Download completed successfully')
                return True

            except (urllib.error.URLError, socket.timeout) as e:
                retry_count += 1
                if retry_count >= self.retry_count:
                    self.logger.error(f'Failed after {retry_count} retries: {e}')
                    return False

                self.logger.warning(f'Retry {retry_count}/{self.retry_count} after error: {e}')
                time.sleep(self.retry_wait)

    def _print_progress(self, downloaded, total_size):
        """Print download progress"""
        if total_size:
            percent = downloaded / total_size * 100
            progress = f'\rProgress: {downloaded}/{total_size} bytes ({percent:.1f}%)'
            sys.stdout.write(progress)
            sys.stdout.flush()

    def run(self):
        """Main entry point"""
        args = self.parse_args()
        self.setup_logging(args.verbose)

        if args.quiet:
            self.logger.setLevel(logging.WARNING)

        self.timeout = args.timeout

        # Handle cookies
        self.load_cookies_from_file(args.load_cookies)

        # Determine output filename
        output_file = args.output_document or self.get_filename_from_url(args.url)

        # Download the file
        success = self.download_file(args.url, output_file)

        # Save cookies if requested
        self.save_cookies_to_file(args.save_cookies)

        return 0 if success else 1

def main():
    wget = WgetSSL()
    sys.exit(wget.run())

if __name__ == '__main__':
    main()

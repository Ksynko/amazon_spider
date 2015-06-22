import string
import urllib
import urlparse
from itertools import islice

from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.log import ERROR, WARNING, INFO

from spiders.items import ProductItem
from __init__ import cond_set, cond_set_value

try:
    from captcha_solver import CaptchaBreakerWrapper
except Exception as e:
    print '!!!!!!!!Captcha breaker is not available due to: %s' % e
    class CaptchaBreakerWrapper(object):
        @staticmethod
        def solve_captcha(url):
            msg("CaptchaBreaker in not available for url: %s" % url,
                level=WARNING)
            return None

class AmazonSpider(Spider):
    name = 'amazon'
    allowed_domains = ["amazon.com"]
    start_urls = []

    SEARCH_URL = 'http://www.amazon.com/s/ref=sr_as_oo?' \
                 'rh=i%3Aaps%2Ck%3A{search_term}&keywords={search_term}'

    MAX_RETRIES = 3

    user_agent = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:35.0) Gecko'
                  '/20100101 Firefox/35.0')

    USER_AGENTS = {
        'default': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:35.0) '\
            'Gecko/20100101 Firefox/35.0',
        'desktop': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:35.0) '\
            'Gecko/20100101 Firefox/35.0',
        'iphone_ipad': 'Mozilla/5.0 (iPhone; CPU iPhone OS 7_0_6 '\
            'like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) '\
            'Version/7.0 Mobile/11B651 Safari/9537.53',
        'android_phone': 'Mozilla/5.0 (Android; Mobile; rv:35.0) '\
            'Gecko/35.0 Firefox/35.0',
        'android_pad': 'Mozilla/5.0 (Android; Tablet; rv:35.0) '\
            'Gecko/35.0 Firefox/35.0',
        'android': 'Mozilla/5.0 (Android; Tablet; rv:35.0) '\
            'Gecko/35.0 Firefox/35.0',
    }

    def __init__(self,
                 url_formatter=None,
                 quantity=None,
                 searchterms_str=None, searchterms_fn=None,
                 site_name=None,
                 product_url=None,
                 user_agent=None,
                 captcha_retries='10',
                 *args, **kwargs):
        if user_agent is None or user_agent not in self.USER_AGENTS.keys():
            self.log("Not available user agent type or it wasn't set."
                     " Default user agent will be used.", INFO)
            user_agent = 'default'

        if user_agent:
            self.user_agent = self.USER_AGENTS[user_agent]
            self.user_agent_key = user_agent

        super(AmazonSpider, self).__init__(*args, **kwargs)

        if site_name is None:
            assert len(self.allowed_domains) == 1, \
                "A single allowed domain is required to auto-detect site name."
            self.site_name = self.allowed_domains[0]
        else:
            self.site_name = site_name

        if url_formatter is None:
            self.url_formatter = string.Formatter()
        else:
            self.url_formatter = url_formatter

        if quantity is None:
            self.log("No quantity specified. Will retrieve all products.",
                     INFO)
            import sys
            self.quantity = sys.maxint
        else:
            self.quantity = int(quantity)

        self.product_url = product_url

        self.searchterms = []
        if searchterms_str is not None:
            self.searchterms = searchterms_str.decode('utf-8').split(',')
        elif searchterms_fn is not None:
            with open(searchterms_fn, encoding='utf-8') as f:
                self.searchterms = f.readlines()
        else:
            self.log("No search terms provided!", ERROR)

        self.log("Created for %s with %d search terms."
                 % (self.site_name, len(self.searchterms)), INFO)

        self.captcha_retries = int(captcha_retries)
        self._cbw = CaptchaBreakerWrapper()

    def make_requests_from_url(self, _):
        """This method does not apply to this type of spider so it is overriden
        and "disabled" by making it raise an exception unconditionally.
        """
        raise AssertionError("Need a search term.")

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

    def parse(self, response):
        if self._has_captcha(response):
            result = self._handle_captcha(response, self.parse)
        else:
            result = self.parse_without_captcha(response)
        return result

    def parse_without_captcha(self, response):
        if self._search_page_error(response):
            remaining = response.meta['remaining']
            search_term = response.meta['search_term']

            self.log("For search term '%s' with %d items remaining,"
                     " failed to retrieve search page: %s"
                     % (search_term, remaining, response.request.url),
                     WARNING)
        else:
            prods_count = -1  # Also used after the loop.
            for prods_count, request_or_prod in enumerate(
                    self._get_products(response)):
                yield request_or_prod
            prods_count += 1  # Fix counter.

            request = self._get_next_products_page(response, prods_count)
            if request is not None:
                yield request

    def _get_products(self, response):
        remaining = response.meta['remaining']
        search_term = response.meta['search_term']
        print search_term
        total_matches = response.meta.get('total_matches')

        prods = self._scrape_product_links(response)

        if total_matches is None:
            total_matches = self._scrape_total_matches(response)
            if total_matches is not None:
                response.meta['total_matches'] = total_matches
                self.log("Found %d total matches." % total_matches, INFO)
            else:
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to parse total matches for %s" % response.url,ERROR)
        print prods
        for i, (prod_item) in enumerate(islice(prods, 0, remaining)):
            # Initialize the product as much as possible.
            # prod_item['site'] = self.site_name
            prod_item['keyword'] = search_term
            prod_item['total_matches'] = total_matches
            # prod_item['results_per_page'] = prods_per_page
            # prod_item['scraped_results_per_page'] = scraped_results_per_page
            # The ranking is the position in this page plus the number of
            # products from other pages.
            prod_item['rank'] = (i + 1) + (self.quantity - remaining)
            # if self.user_agent_key not in ["desktop", "default"]:
            #     prod_item['is_mobile_agent'] = True
            yield prod_item
            # elif isinstance(prod_url, Request):
            #     cond_set_value(prod_item, 'url', prod_url.url)  # Tentative.
            #     yield prod_url
            # else:
            #     # Another request is necessary to complete the product.
            #     url = urlparse.urljoin(response.url, prod_url)
            #     cond_set_value(prod_item, 'url', url)  # Tentative.
            #     yield Request(
            #         url,
            #         callback=self.parse_product,
            #         meta={'product': prod_item},
            #     )

    def _get_next_products_page(self, response, prods_found):
        link_page_attempt = response.meta.get('link_page_attempt', 1)

        result = None
        if prods_found is not None:
            # This was a real product listing page.
            remaining = response.meta['remaining']
            remaining -= prods_found
            if remaining > 0:
                next_page = self._scrape_next_results_page_link(response)
                if next_page is None:
                    pass
                elif isinstance(next_page, Request):
                    next_page.meta['remaining'] = remaining
                    result = next_page
                else:
                    url = urlparse.urljoin(response.url, next_page)
                    new_meta = dict(response.meta)
                    new_meta['remaining'] = remaining
                    result = Request(url, self.parse, meta=new_meta, priority=1)
        elif link_page_attempt > self.MAX_RETRIES:
            self.log(
                "Giving up on results page after %d attempts: %s" % (
                    link_page_attempt, response.request.url),
                ERROR
            )
        else:
            self.log(
                "Will retry to get results page (attempt %d): %s" % (
                    link_page_attempt, response.request.url),
                WARNING
            )

            # Found no product links. Probably a transient error, lets retry.
            new_meta = response.meta.copy()
            new_meta['link_page_attempt'] = link_page_attempt + 1
            result = response.request.replace(
                meta=new_meta, cookies={}, dont_filter=True)

        return result

    def _scrape_total_matches(self, response):
        if response.css('#noResultsTitle'):
            return 0

        values = response.css('#s-result-count ::text').re(
            '([0-9,]+)\s[Rr]esults for')
        if not values:
            values = response.css('#resultCount > span ::text').re(
                '\s+of\s+(\d+(,\d\d\d)*)\s+[Rr]esults')
            if not values:
                values = response.css(
                    '#result-count-only-next'
                ).xpath(
                    'comment()'
                ).re(
                    '\s+of\s+(\d+(,\d\d\d)*)\s+[Rr]esults\s+'
                )

        if values:
            total_matches = int(values[0].replace(',', ''))
        else:
            if not self.is_nothing_found(response):
                self.log(
                    "Failed to parse total number of matches for: %s"
                    % response.url,
                    level=ERROR
                )
            total_matches = None
        return total_matches

    def _scrape_product_links(self, response):
        products = response.xpath('//li[@class="s-result-item"]')

        for pr in products:
            product = ProductItem()

            cond_set(product, 'title',
                     pr.xpath('.//h2/../@title').extract())

            cond_set(product, 'product_image',
                     pr.xpath('.//img[@alt="Product Details"]/@src').extract())

            cond_set(product, 'brand',
                     pr.xpath(
                         './/div[@class="a-fixed-left-grid-col a-col-right"]'
                         '/div/div/span[2]/text()').extract())

            cond_set(product, 'price',
                     pr.xpath(
                        './/span[contains(@class,"s-price")]/text()'
                     ).extract())

            cond_set(product, 'asin', pr.xpath('@data-asin').extract())



            yield product

    def _scrape_next_results_page_link(self, response):
        next_pages = response.css('#pagnNextLink ::attr(href)').extract()
        next_page_url = None
        if len(next_pages) == 1:
            next_page_url = next_pages[0]
        elif len(next_pages) > 1:
            self.log("Found more than one 'next page' link.", ERROR)
        return next_page_url

    def is_nothing_found(self, response):
        txt = response.xpath('//h1[@id="noResultsTitle"]/text()').extract()
        txt = ''.join(txt)
        return 'did not match any products' in txt

    def _search_page_error(self, response):
        body = response.body_as_unicode()
        return "Your search" in body \
            and  "did not match any products." in body

    # Captcha handling functions.
    def _has_captcha(self, response):
        return '.images-amazon.com/captcha/' in response.body_as_unicode()

    def _solve_captcha(self, response):
        forms = response.xpath('//form')
        assert len(forms) == 1, "More than one form found."

        captcha_img = forms[0].xpath(
            '//img[contains(@src, "/captcha/")]/@src').extract()[0]

        self.log("Extracted capcha url: %s" % captcha_img, level=DEBUG)
        return self._cbw.solve_captcha(captcha_img)

    def _handle_captcha(self, response, callback):
        captcha_solve_try = response.meta.get('captcha_solve_try', 0)
        url = response.url
        self.log("Captcha challenge for %s (try %d)."
                 % (url, captcha_solve_try),
                 level=INFO)

        captcha = self._solve_captcha(response)

        if captcha is None:
            self.log(
                "Failed to guess captcha for '%s' (try: %d)." % (
                    url, captcha_solve_try),
                level=ERROR
            )
            result = None
        else:
            self.log(
                "On try %d, submitting captcha '%s' for '%s'." % (
                    captcha_solve_try, captcha, url),
                level=INFO
            )
            meta = response.meta.copy()
            meta['captcha_solve_try'] = captcha_solve_try + 1
            result = FormRequest.from_response(
                response,
                formname='',
                formdata={'field-keywords': captcha},
                callback=callback,
                dont_filter=True,
                meta=meta)

        return result
# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy import Item, Field


class ProductItem(Item):
    # define the fields for your item here like:
    keyword = Field()
    total_matches = Field()

    product_image = Field()
    title = Field()
    rank = Field()
    brand = Field()
    price = Field()
    asin = Field()
    prime = Field()
    shiping_price = Field()
    new_price = Field()
    new_offers = Field()
    used_price = Field()
    used_offers = Field()
    rating = Field()
    number_of_reviews = Field()
    category = Field()
    number_of_items = Field()

    url = Field()

from google.cloud import logging as gc_logging
import pandas as pd
from googlesearch import search, get_tbs
import os, logging
from install_playwright import install
# from selenium import webdriver
# import chromedriver_binary  

import json
from parsel import Selector
from playwright.sync_api import sync_playwright

class GCloudConnection:

    def __init__(self, URL, LOG_NAME):
        # env variable declared only for gcloud authentication during local tests. Not necessary at deployed instances
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = '../prefab-mile-237211-20455cdbfdab.json'
        logging.getLogger().setLevel(logging.INFO)
        self.connect_cloud_services(LOG_NAME)
        self.URL = URL

    def connect_cloud_services(self, LOG_NAME):
            # connect gcloud logger to default logging.
            logging_client = gc_logging.Client()
            logging_client.get_default_handler()
            logging_client.setup_logging()
            logging_client.logger(LOG_NAME)

class Scraper:

    def __init__(self):
        self.script =  """

        async function scrollPage2(scrollElements) {
            let items = [];
            scrollContainer = document.querySelector("[jsaction^='focus: scrollable.focus;']")
            let previousHeight = await page.evaluate(`document.querySelector("${scrollContainer}").scrollHeight`);
            while (itemTargetCount > items.length) {
                await page.evaluate(`document.querySelector("${scrollContainer}").scrollTo(0, document.querySelector("${scrollContainer}").scrollHeight)`);
                await page.evaluate(`document.querySelector("${scrollContainer}").scrollHeight > ${previousHeight}`);
                await page.waitForTimeout(2000);
            }
            return items
        }

        async function scrollPage(page, scrollElements) {
            let currentElement = 0;
            while (true) {
                let elementsLength = await page.evaluate((scrollElements) => {
                return document.querySelectorAll(scrollElements).length;
                }, scrollElements);
                for (; currentElement < elementsLength; currentElement++) {
                await page.waitForTimeout(200);
                await page.evaluate(
                    (currentElement, scrollElements) => {
                    document.querySelectorAll(scrollElements)[currentElement].scrollIntoView();
                    },
                    currentElement,
                    scrollElements
                );
                }
                await page.waitForTimeout(5000);
                let newElementsLength = await page.evaluate((scrollElements) => {
                return document.querySelectorAll(scrollElements).length;
                }, scrollElements);
                if (newElementsLength === elementsLength) break;
            }
        }

        function waitCss(selector, n=1, require=false, timeout=5000) {
            "aria-label='Résultats pour"
            console.log(selector, n, require, timeout);
            var start = Date.now();
            while (Date.now() - start < timeout){
                if (document.querySelectorAll(selector).length >= n){
                    return document.querySelectorAll(selector);
                }
                else{
                    scrollPage2()
                }
            }
            if (require){
                throw new Error(`selector "${selector}" timed out in ${Date.now() - start} ms`);
            } else {
                return document.querySelectorAll(selector);
            }
        }

        var results = waitCss("div[role*=article]>a", n=100000, require=false);
        return Array.from(results).map((el) => el.getAttribute("href"))
        """


    # runs same query filtering by every date in date range
    def scrape(self, job, number_of_urls = 10):
        query, from_date, to_date, type = job.values()
        urls = []
        for d in pd.date_range(from_date, to_date):
            tbs = get_tbs(from_date=d, to_date=d) #"%Y-%m-%d"
            results = search(query, tbs=tbs, pause=2, stop=number_of_urls)
            for url in results:
                urls.append({"date" : d.date(), "url" : url})
        return pd.read_json(urls, columns=["date", "url"])


    def scrape_maps(self,query):
        with sync_playwright() as p:
            # if not hasattr(self, "browser"): # instancié une sele fois
            browser = p.chromium.launch(headless=False, slow_mo=500)
            page = browser.new_page()


            url = f"https://www.google.com/maps/search/{query['query'].replace(' ', '+')}/?hl=fr"
            page.goto(url)
            
            # Pour accepter les cookies google
            page.on("dialog", lambda dialog: dialog.accept())
            page.click("button:has-text(\"Tout refuser\")")

            # On recupere tout les liens de la recherche
            urls = page.evaluate("() => {" + self.script + "}")


            print(f"on a trouvé pour cette recherche {query} {len(urls)} resultats")

            places = []
            for url in urls:
                page.goto(url)
                page.wait_for_selector("button[jsaction='pane.rating.category']")
                places.append(self.parse_place(Selector(text=page.content())))
        print(json.dumps(places, indent=2, ensure_ascii=False))

        return pd.DataFrame.from_dict(places)



    def filename(self, job):
        #stock, keywords, from_date, to_date, type = job.values()
        #filename = f"{stock}/{stock}_{from_date}_{to_date}.csv"
        query, from_date, to_date, type = job.values()
        filename = f"{query}_{from_date}_{to_date}.csv"
        return filename
    


    def parse_place(self,selector):
        """parse Google Maps place"""
    
        def aria_with_label(label):
            """gets aria element as is"""
            try:
                return selector.css(f"*[aria-label*='{label}']::attr(aria-label)")
            except Exception as e:
                return 'err:' + str(e)

        def aria_no_label(label):
            """gets aria element as text with label stripped off"""
            try:
                texts = aria_with_label(label).getall()
                print(texts)

                #On prend le premier match [0] 
                return texts[0].split(label, 1)[1].strip()
            except Exception as e:
                return 'err:' + str(e)
        
        result = {
            "name": "".join(selector.css("h1 ::text").getall()).strip(),
            "category": selector.css("button[jsaction='pane.rating.category']::text").get(),
            # most of the data can be extracted through accessibility labels:
            "address": aria_no_label("Adresse: "),
            "website": aria_no_label("Site Web: "),
            "phone": aria_no_label("Numéro de téléphone: "),
            "review_count": aria_with_label(" étoiles").get(),
            "work_hours": aria_with_label("lundi, ").get().split(". Masquer")[0] if aria_with_label("lundi, ").get() else "",
            # to extract star numbers from text we can use regex pattern for numbers: "\d+"
            # "stars": aria_with_label(" étoiles").re("\d+.*\d+")[0],
            # "5_stars": aria_with_label("5 étoiles").re(r"(\d+) avis")[0],
            # "4_stars": aria_with_label("4 étoiles").re(r"(\d+) avis")[0],
            # "3_stars": aria_with_label("3 étoiles").re(r"(\d+) avis")[0],
            # "2_stars": aria_with_label("2 étoiles").re(r"(\d+) avis")[0],
            # "1_stars": aria_with_label("1 étoiles").re(r"(\d+) avis")[0],
        }
        return result
    
from google.cloud import logging as gc_logging
import pandas as pd
from googlesearch import search, get_tbs
import os, logging
from install_playwright import install
import time
# from selenium import webdriver
# import chromedriver_binary  

import json
from parsel import Selector
from playwright.sync_api import sync_playwright

class GCloudConnection:

    def __init__(self, URL, LOG_NAME):
        # env variable declared only for gcloud authentication during local tests. Not necessary at deployed instances
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = '../sandbox-azaki-a48d4c3efa57.json'
        if "CLOUD" not in os.environ:
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
function load () {{
    async function scrollPage2(scrollContainer, selector, n=12, timeout=5000) {{
        var start = Date.now();
        //scrollContainer = document.querySelector('[aria-label^="Résultats pour"]')
        let previousHeight = scrollContainer.scrollHeight;
        //previousHeight*7 > scrollContainer.scrollHeight
        while (document.querySelectorAll(selector).length >= n || (Date.now() - start < timeout) ) {{
            scrollContainer.scrollTo(0, scrollContainer.scrollHeight);
            await new Promise(r => setTimeout(r, 200));
        }}
    }}

    function waitCss(selector, n=1, require=false, timeout=5000) {{
        var start = Date.now();
        while (Date.now() - start < timeout){{
            if (document.querySelectorAll(selector).length >= n){{
                return document.querySelectorAll(selector);
            }}
            // else{{
            //     await scrollPage2(document.querySelector('[aria-label^="Résultats pour"]'), selector, n=n, timeout=n*200)
            // }}
        }}
        if (require){{
            throw new Error("err");
        }} else {{
            return document.querySelectorAll(selector);
        }}
    }}
    selector = "div[jsaction^='mouseover:pane']>a"
    scrollPage2(document.querySelector('[aria-label^="Résultats pour"]'), selector, n={nb}, timeout={nb}*200)
    results = waitCss(selector, n={nb}, require=false, timeout={nb}*200);
    return Array.from(results).map( (el) => el.getAttribute("href")) 
}}
    """


    # runs same query filtering by every date in date range
    def scrape(self, job, number_of_urls = 10):
        query, from_date, to_date, nb_results, type = job.values()
        urls = []
        for d in pd.date_range(from_date, to_date):
            tbs = get_tbs(from_date=d, to_date=d) #"%Y-%m-%d"
            results = search(query, tbs=tbs, pause=2, stop=number_of_urls)
            for url in results:
                urls.append({"date" : d.date(), "url" : url})
        return pd.read_json(urls, columns=["date", "url"])


    def scrape_maps(self,query, number_of_urls = 10):
        with sync_playwright() as p:
            # if not hasattr(self, "browser"): # instancié une sele fois
            browser = p.chromium.launch()#(headless=False, slow_mo=500)
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/69.0.3497.100 Safari/537.36"
            )
            context = browser.new_context(user_agent=ua)
            context.tracing.start(screenshots=True, snapshots=True)
            context.tracing.start_chunk()

            page = context.new_page()#(user_agent=ua)

            
            url = f"https://www.google.com/maps/search/{query['query'].replace(' ', '+')}/?hl=fr"
            page.goto(url)
            
            # Pour accepter les cookies google
            page.on("dialog", lambda dialog: dialog.accept())
            page.click('input[value="Tout refuser"]') 
            context.tracing.stop_chunk(path = "trace_consent.zip")

            context.tracing.start_chunk()
            # On recupere tout les liens de la recherche
            page.wait_for_selector('[aria-label^="Résultats pour"]', timeout=10000)
            
            urls = page.evaluate( self.script.format(nb=number_of_urls) )
            # on attend timeout seconds qu'il y ai assez de liens
            # si moins que number_of_urls alors on retourne tout ce qu'il y a
            timeout = 60*3   # [seconds]
            timeout_start = time.time()
            while ( time.time() < timeout_start + timeout ):
                urls = page.evaluate( self.script.format(nb=number_of_urls) )
                if ( len(urls) < int(number_of_urls) ):
                    break # nombre de liens OK
                print('len of urls: ', len(urls))
                time.sleep(1)
            
            context.tracing.stop_chunk(path = "trace_urls.zip")

            context.tracing.start_chunk()

            print(f"on a trouvé pour cette recherche {query} {len(urls)} resultats")

            places = []
            for url in urls:
                page.goto(url)
                page.wait_for_selector("button[jsaction='pane.rating.category']")
                places.append(self.parse_place(Selector(text=page.content())))

            context.tracing.stop_chunk(path = "trace_maps.zip")
            # context.tracing.stop(path = "trace.zip")

        print(json.dumps(places, indent=2, ensure_ascii=False))


        return pd.DataFrame.from_dict(places)



    def filename(self, job):
        #stock, keywords, from_date, to_date, nb_results, type = job.values()
        #filename = f"{stock}/{stock}_{from_date}_{to_date}.csv"
        query, from_date, to_date, nb_results, type = job.values()
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
    
import random
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import requests
import sys
from config import *
import re
import hashlib
import os
import shutil
import json
from selenium.webdriver import Keys
from selenium import webdriver
from mailjet_rest import Client
import sqlite3

adspower_url = 'http://local.adspower.net:50325'
open_url = adspower_url + '/api/v1/browser/start?user_id='
close_url = adspower_url + '/api/v1/browser/stop'
delete_url = adspower_url + '/api/v1/user/delete'
create_url = adspower_url + '/api/v1/user/create'
open_status_url = adspower_url + '/api/v1/browser/active'

kijjiji_url = 'https://www.kijiji.ca/'
kijjiji_post_url = kijjiji_url + 'p-select-category.html'
kijjiji_ads_url = kijjiji_url + 'm-my-ads/active/'


def get_sqlite_conn():
    try:
        conn = sqlite3.connect(sqlite_db_name)
        return conn
    except Exception as e:
        print(e)
        return False


def sqlite_exec(sql_query, params=None):
    try:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        if params:
            ret = cursor.execute(sql_query, params)
        else:
            ret = cursor.execute(sql_query)
        cursor.close()
        conn.commit()
        conn.close()
        if not ret:
            return False
        return True
    except Exception as e:
        print(e)
        return False


def sqlite_query(sql_query, params=None):
    try:
        conn = get_sqlite_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if params:
            ret = cursor.execute(sql_query, params).fetchall()
        else:
            ret = cursor.execute(sql_query).fetchall()
        cursor.close()
        conn.commit()
        conn.close()
        if not ret:
            return False
        return ret
    except Exception as e:
        print(e)
        return False


def element_exists(driver, css):
    try:
        driver.find_element(By.CSS_SELECTOR, css)
    except NoSuchElementException:
        return False
    return True


def wait_for_element(driver, css):
    for i in range(0, 15):
        if element_exists(driver, css):
            small_sleep()
            return True
        time.sleep(2)
    if not element_exists(driver, css):
        driver.refresh()
        for i in range(0, 15):
            if element_exists(driver, css):
                small_sleep()
                return True
            time.sleep(2)
    if not element_exists(driver, css):
        raise NoSuchElementException(css)


def small_sleep():
    time.sleep(random.randint(2, 3))


def medium_sleep():
    time.sleep(random.randint(5, 8))


def get_ads_power_driver(profile_id, headless=False):
    try:
        if headless:
            params = {'open_tabs': 1, 'headless': 1}
        else:
            params = {'open_tabs': 1}
        resp = requests.get(open_url + profile_id, params=params).json()
        while resp["code"] != 0:
            resp = requests.get(open_url + profile_id, params=params).json()
            time.sleep(10)
        chrome_driver = resp["data"]["webdriver"]
        service = ChromeService(executable_path=chrome_driver)
        chrome_options = ChromeOptions()
        chrome_options.add_experimental_option("debuggerAddress", resp["data"]["ws"]["selenium"])
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.maximize_window()
        driver.switch_to.window(driver.window_handles[0])
        return driver
    except Exception as e:
        print(e)
        sys.exit(1)


def close_adspower_driver(profile_id):
    try:
        params = {'user_id': profile_id}
        resp = requests.get(close_url, params=params).json()
        if resp['code'] != 0:
            print('Not able to close browser: ' + profile_id + ': ' + resp['msg'])
            return False
        return True
    except Exception as e:
        print(e)
        return False


def get_listing_failed_template(address, mls_id):
    template = "Kijiji bot couldn't post the ad for {} with MLS# {}. Check the data and try again or post it manually.".format(address, str(mls_id))
    return template


def send_email(message):
    try:
        mailjet = Client(auth=(mailjet_api_key, mailjet_api_secret), version='v3.1')
        data = {
            'Messages': [
                {
                    "From": {
                        "Email": mailjet_from_address,
                        "Name": "Kijjiji Bot"
                    },
                    "To": [
                        {
                            "Email": mailjet_to_address,
                            "Name": "You"
                        }
                    ],
                    "Subject": "Kijjiji Listing Failed",
                    "TextPart": message
                }
            ]
        }
        mailjet.send.create(data=data)
        return True
    except Exception as e:
        print(e)
        return False


def db_init():
    try:
        sql_query = """CREATE TABLE IF NOT EXISTS "listings" (
                        "id"	INTEGER NOT NULL,
                        "data"	TEXT NOT NULL,
                        "mls_id"	INTEGER NOT NULL,
                        PRIMARY KEY("id" AUTOINCREMENT)
                    );"""
        sqlite_exec(sql_query)
        sql_query = """CREATE TABLE IF NOT EXISTS "removals" (
                        "id"	INTEGER NOT NULL,
                        "data"	TEXT NOT NULL,
                        "mls_id"	INTEGER NOT NULL,
                        PRIMARY KEY("id" AUTOINCREMENT)
                    );"""
        sqlite_exec(sql_query)
    except Exception as e:
        print(e)
        sys.exit(1)


def db_listing_exists(mls_ids):
    try:
        sql_query = "SELECT * FROM listings WHERE mls_id=?"
        params = (mls_ids,)
        if not sqlite_query(sql_query, params):
            return False
        return True
    except Exception as e:
        print(e)
        sys.exit(1)


def db_removal_exists(mls_ids):
    try:
        sql_query = "SELECT * FROM removals WHERE mls_id=?"
        params = (mls_ids,)
        if not sqlite_query(sql_query, params):
            return False
        return True
    except Exception as e:
        print(e)
        sys.exit(1)


def db_add_listings(listings):
    try:
        for listing in listings:
            sql_query = "INSERT INTO listings (data, mls_id) VALUES (?, ?)"
            params = (json.dumps(listing), listing['mls_id'])
            if db_listing_exists(listing['mls_id']):
                continue
            if not sqlite_exec(sql_query, params):
                raise Exception('Could not add listing to database')
        return True
    except Exception as e:
        print(e)
        return False


def db_remove_listing(mls_id):
    try:
        sql_query = "DELETE FROM listings WHERE mls_id=?"
        params = (mls_id,)
        sqlite_exec(sql_query, params)
        return True
    except Exception as e:
        print(e)
        return False


def db_remove_removal(mls_id):
    try:
        sql_query = "DELETE FROM removals WHERE mls_id=?"
        params = (mls_id,)
        sqlite_exec(sql_query, params)
        return True
    except Exception as e:
        print(e)
        return False


def db_get_listings():
    try:
        sql_query = 'SELECT * FROM listings'
        listings = sqlite_query(sql_query)
        if not listings:
            return False
        listings_array = []
        for listing in listings:
            listings_array.append(json.loads(listing['data']))
        return listings_array
    except Exception as e:
        print(e)
        sys.exit(1)


def db_get_removals():
    try:
        sql_query = 'SELECT * FROM removals'
        listings = sqlite_query(sql_query)
        if not listings:
            return False
        listings_array = []
        for listing in listings:
            listings_array.append(json.loads(listing['data']))
        return listings_array
    except Exception as e:
        print(e)
        sys.exit(1)


def db_add_removals(listings):
    try:
        for listing in listings:
            sql_query = "INSERT INTO removals (data, mls_id) VALUES (?, ?)"
            params = (json.dumps(listing), listing['mls_id'])
            if db_removal_exists(listing['mls_id']):
                continue
            if not sqlite_exec(sql_query, params):
                raise Exception('Could not add removal to database')
        return True
    except Exception as e:
        print(e)
        return False


def run_listings_bot():
    while True:
        try:
            listings = db_get_listings()
            removals = db_get_removals()
            if listings or removals:
                driver = get_ads_power_driver(kijjiji_profile_id)
                if listings:
                    for listing in listings:
                        kijjiji_post_listing(driver, listing)
                if removals:
                    for removal in removals:
                        kijjiji_remove_listing(driver, removal)
                close_adspower_driver(kijjiji_profile_id)
            time.sleep(5)
        except Exception as e:
            print(e)
            time.sleep(5)


def kijjiji_post_listing(driver, listing):
    try:
        driver.get(kijjiji_post_url)

        # AD TITLE
        wait_for_element(driver, '#AdTitleForm')
        driver.find_element(By.ID, 'AdTitleForm').send_keys(listing['ad_title'])
        small_sleep()
        driver.find_element(By.CSS_SELECTOR, 'div[class^="titleFormContainer"] button').click()
        small_sleep()

        # AD CATEGORY
        category_btns = driver.find_elements(By.CSS_SELECTOR, 'div[class^="allCategoriesContainer"] button')
        for category_btn in category_btns:
            if category_btn.text.lower().strip() == 'real estate':
                category_btn.click()
                break
        small_sleep()
        category = listing['category']
        if re.findall('sale', category, re.I):
            category_keyword = 'sale'
        else:
            category_keyword = 'rent'
        category_btns = driver.find_elements(By.CSS_SELECTOR, 'ul[class^="categoryList"] button')
        for category_btn in category_btns:
            if re.findall(category_keyword, category_btn.text.lower().strip(), re.I):
                category_btn.click()
                break
        small_sleep()
        category_btns = driver.find_elements(By.CSS_SELECTOR, 'ul[class^="categoryList"] button')
        for category_btn in category_btns:
            if category_btn.text.strip() == category:
                category_btn.click()
                break
        medium_sleep()
        wait_for_element(driver, '#adType1')

        # EXTENDED OPTIONS
        if element_exists(driver, 'label[for="forsalebyhousing_s-1"]'):
            driver.find_element(By.CSS_SELECTOR, 'label[for="forsalebyhousing_s-1"]').click()
        if element_exists(driver, 'label[for="forrentbyhousing_s-1"]'):
            driver.find_element(By.CSS_SELECTOR, 'label[for="forrentbyhousing_s-1"]').click()
        small_sleep()

        if element_exists(driver, 'select[id^="numberbedrooms"]'):
            driver.find_element(By.CSS_SELECTOR, 'select[id^="numberbedrooms"]').click()
            small_sleep()
            bed_number_options = driver.find_elements(By.CSS_SELECTOR, 'select[id^="numberbedrooms"] option')
            for bed_number_option in bed_number_options:
                if bed_number_option.text.strip() == listing['beds']:
                    bed_number_option.click()
                    break
            small_sleep()

        if element_exists(driver, 'select[id^="numberbathrooms"]'):
            driver.find_element(By.CSS_SELECTOR, 'select[id^="numberbathrooms"]').click()
            small_sleep()
            bath_number_options = driver.find_elements(By.CSS_SELECTOR, 'select[id^="numberbathrooms"] option')
            for bath_number_option in bath_number_options:
                if bath_number_option.text.strip() == listing['baths']:
                    bath_number_option.click()
                    break
            small_sleep()

        if element_exists(driver, 'input[id^="areainfeet"]'):
            driver.find_element(By.CSS_SELECTOR, 'input[id^="areainfeet"]').send_keys(listing['sqft'])
            small_sleep()

        # ALL LISTINGS
        driver.find_element(By.ID, 'pstad-descrptn').send_keys(listing['description'])
        small_sleep()
        image_download_dir_name = hashlib.md5(str(random.randint(10000000, 99999999999)).encode()).hexdigest()
        image_download_dir = os.getcwd() + os.sep + image_download_dir_name
        os.mkdir(image_download_dir)
        images = listing['images']
        listing_images = ""
        for image in images:
            image_filename = hashlib.md5(str(random.randint(10000000, 99999999999)).encode()).hexdigest() + '.jpeg'
            image_location = image_download_dir + os.sep + image_filename
            response = requests.get(image, stream=True)
            if response.status_code == 200:
                with open(image_location, 'wb') as f:
                    shutil.copyfileobj(response.raw, f)
                    listing_images += image_location + "\n"
        listing_images = listing_images.strip()
        driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys(listing_images)
        time.sleep(60)
        try:
            driver.find_element(By.ID, 'YoutubeURL').send_keys(listing['youtube'])
        except:
            pass
        small_sleep()
        driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Change my location"]').click()
        small_sleep()
        driver.find_element(By.ID, 'location').send_keys(Keys.BACKSPACE)
        small_sleep()
        driver.find_element(By.ID, 'location').send_keys(listing['postalCode'])
        small_sleep()
        postal_code_keyword = listing['postalCode'][0:3] + ' ' + listing['postalCode'][3:6]
        location_selectors = driver.find_elements(By.CSS_SELECTOR, 'div[id^="LocationSelector"]')
        location_found = 0
        for location_selector in location_selectors:
            if re.findall(postal_code_keyword, location_selector.text, re.I | re.M):
                location_selector.click()
                location_found = 1
                break
        if not location_found:
            raise Exception('Listing not found')
        small_sleep()
        driver.find_element(By.ID, 'PriceAmount').send_keys(listing['price'])
        small_sleep()
        driver.find_element(By.CSS_SELECTOR, 'button[data-qa-id="package-0-bottom-select"]').click()
        small_sleep()
        post_btns = driver.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
        for post_btn in post_btns:
            if post_btn.text.lower().strip() == 'post your ad':
                post_btn.click()
                break
        small_sleep()
        shutil.rmtree(image_download_dir)
        db_remove_listing(listing['mls_id'])
        small_sleep()
        wait_for_element(driver, '#ViewItemPage')
        return True
    except Exception as e:
        print(e)
        email_template = get_listing_failed_template(listing['address'], listing['mls_id'])
        send_email(email_template)
        db_remove_listing(listing['mls_id'])
        return False


def kijjiji_remove_listing(driver, removal):
    try:
        mls_id = str(removal['mls_id'])
        driver.get(kijjiji_ads_url)
        wait_for_element(driver, 'table tbody tr')
        small_sleep()
        listings = driver.find_elements(By.CSS_SELECTOR, 'table tbody tr')
        for listing in listings:
            title_text = listing.find_element(By.CSS_SELECTOR, 'td[class^="titleCell"]').text.strip()
            if re.findall(mls_id, title_text, re.I | re.M):
                driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Delete Ad"]').click()
                small_sleep()
                wait_for_element(driver, 'div[class^="deleteModalContainer"]')
                modal_options_selector = 'div[class^="deleteModalContainer"] span[class^="optionContainer"]'
                options = driver.find_elements(By.CSS_SELECTOR, modal_options_selector)
                for option in options:
                    if option.text.lower().strip() == 'prefer not to say':
                        option.click()
                        small_sleep()
                        driver.find_element(By.CSS_SELECTOR, 'div[class^="deleteModalContainer"] div > button').click()
                        small_sleep()
                        break
                break
        db_remove_removal(str(removal['mls_id']))
        return True
    except Exception as e:
        print(e)
        db_remove_removal(str(removal['mls_id']))
        return False

from genericpath import isfile
from xmlrpc.client import DateTime
from webdriver_manager.chrome import ChromeDriverManager

import sqlite3

from logging import raiseExceptions

import datetime
import os
import tkinter as tk
import configparser

from time import sleep

import pickle

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

done = False

def create_db(cur):
    cur.execute('''CREATE TABLE renews(
    datetime NUMERIC PRIMARY KEY,
    action TEXT
    );''')


def getDriver(headless=True):
    locale = "it"
    chrome_options = Options()
    chrome_options.add_argument(f"--lang={locale}")
    chrome_options.add_argument("start-maximized")
    if headless:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
    chrome_prefs = {}
    #chrome_prefs["profile.managed_default_content_settings"] = {"javascript": 2}
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    chrome_prefs["profile.managed_default_content_settings"] = {"images": 2}
    chrome_options.add_experimental_option('prefs', chrome_prefs)
    #chrome_options.add_argument("user-data-dir=selenium")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--incognito")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    sleep(2)
    return driver


def renew_service(driver):    
    #TODO click su renew service ogni domenica
    try:
        driver.find_element(By.CSS_SELECTOR, "button.ddns-button.clr-azzurro[value='confirmHost']").click()
        lastConfirm = datetime.datetime.strptime(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "span#lastConfirm").text, "%d-%m-%Y %H:%M:%S")))
        try:
            cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (lastConfirm, "Confermed"))
            con.commit()
        except sqlite3.IntegrityError:
            pass
        return True
    except NoSuchElementException:
        cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "ERROR: Confirm button Not Found"))
        con.commit()
        return False
        

def login(config, headless=True, withCookies = False):
    config.read('./.settings/config.ini')

    driver = getDriver(headless)
    if withCookies:
        try:
            cookies = pickle.load(open("./.settings/dyndns.pkl", "rb"))
        except FileNotFoundError:
            driver.close()
            login(config, headless, withCookies=False)
        driver.get("https://dyndns.it/host-management/")
        driver.delete_all_cookies()
        for cookie in cookies:
            driver.add_cookie(cookie)
        sleep(8)
        driver.refresh()
        
    else:
        driver.get("https://dyndns.it/host-management/")
        user = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@id='log']")))
        user.send_keys(str(config['DEFAULT']['user']).strip())
        driver.find_element(By.XPATH, "//input[@id='pwd']").send_keys(str(config['DEFAULT']['pwd']).strip())
        driver.find_element(By.XPATH, "//label[@for='rememberme']").click()
        sleep(1)
        driver.find_element(By.XPATH, "//button[@title='Login']").click()
        try:
            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ddns-div-table.ddns-msg.ddns-error")))
            raise KeyError
        except TimeoutException:
            pass
        with open("./.settings/dyndns.pkl","wb") as cookie_file:
            pickle.dump(driver.get_cookies(), cookie_file)
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.nectar-button.medium.extra-color-2.regular-button"))).click()
    except TimeoutException:
        try:
            #TODO vedere se è la pagina dove fare il rinnovo
            #lastConfirm = datetime.datetime.strptime(driver.find_element(By.CSS_SELECTOR, "span#lastConfirm").text, "%d-%m-%Y %H:%M:%S")
            lastConfirm = datetime.datetime.strptime(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "span#lastConfirm"))).text, "%d-%m-%Y %H:%M:%S")
            try:
                cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (lastConfirm, "Confermed"))
                con.commit()
            except sqlite3.IntegrityError:
                pass
        except TimeoutException:
            driver.close()
            if withCookies:
                login(config, headless, withCookies=False)
            cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "ERROR: Confirm page Not Found"))
            con.commit()            
            raiseExceptions("ERROR: Confirm page Not Found")
            
    #res = cur.execute('''SELECT datetime FROM renews WHERE action=="Confermed" ORDER BY datetime DESC;''')
    #date = datetime.datetime.strptime(res.fetchone()[0], "%Y-%m-%d %H:%M:%S")
    if (datetime.datetime.utcnow()-lastConfirm).days > 20:
        renew_service(driver)
    
    return driver


def set_data(error=False):
    dir_bcp = os.getcwd()
    try:
        os.mkdir("./.settings")
        config["DEFAULT"] = {}
    except FileExistsError:
        if not os.path.isfile('./.settings/config.ini'):
            config["DEFAULT"] = {}
    os.chdir("./.settings")
    config.read('./config.ini')


    # TK Windows
    ws = tk.Tk(screenName="settings")
    ws.title("settings")
    ws.geometry('250x150')

    if error:
        tk.Label(text="Nome utente o password errati.\n").pack()
        ws.geometry('250x200')

    def retrieve_input(obj, type):
        inputValue=obj.get("1.0","end-1c")
        if type == "user":
            config["DEFAULT"]["user"] = str(inputValue)
        else:
            config["DEFAULT"]["pwd"] = str(inputValue)

    userBox=tk.Text(ws, height=1, width=20)
    pwdBox=tk.Text(ws, height=1, width=20)

    userBoxCommit=tk.Button(ws, height=1, width=10, text="Commit", 
                        command=lambda: retrieve_input(userBox, 'user'))
    tk.Label(text="USERNAME:").pack()
    userBox.pack()
    userBoxCommit.pack()
    pwdBoxCommit=tk.Button(ws, height=1, width=10, text="Commit", 
                        command=lambda: retrieve_input(pwdBox,'pwd'))
    tk.Label(text="PASSWORD:").pack()
    pwdBox.pack()
    pwdBoxCommit.pack()


    ws.mainloop()
    
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    os.chdir(dir_bcp)
    return


if __name__ == "__main__":
    config = configparser.ConfigParser()

    isdb = os.path.isfile('dyndns.db')
    con = sqlite3.connect('dyndns.db')
    cur = con.cursor()
    if not isdb:
        create_db(cur, config)
    if not os.path.isfile('./.settings/config.ini'):
        set_data()
    print(config)
    while not done:
        try:
            login(config, headless=True, withCookies=True)
            done = True
        except KeyError:
            set_data(error=True)
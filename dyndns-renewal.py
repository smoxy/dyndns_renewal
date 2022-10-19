from genericpath import isfile
from xmlrpc.client import DateTime

import sqlite3

from logging import raiseExceptions

import datetime
import os
import configparser
import getopt
import sys
import platform
import logging

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
V="0.2.2"
#formatter = logging.Formatter('[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s','%m-%d %H:%M:%S')
logging.basicConfig(filename=r'log.log', encoding='utf-8', format='[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s', level=logging.INFO) #'%(asctime)s - %(name)s - %(levelname)s - %(message)s'

shortopts = '''hlciV''' #if after the letter there is ':' so the argument is required
longopts = ["help", "headless", "cookiesless", "noimage", "version"] #if after name variable ther is '=' so the argument is required

def create_db(cur):
    cur.execute('''CREATE TABLE renews(
    datetime NUMERIC PRIMARY KEY,
    action TEXT
    );''')

def help():
    """
    print help window
    """
    print(f"""dyndns-renewal {V}
(C) 2022-2023 Simone Flavio Paris.
Released under the GNU GPLv2.

    -h --help               Print this help screen
    -l --headless           Use this script in headless mode
    -c --cookiesless        Try to login preferring user and password avery time inputting instead of automatic cookies login
    -i --noimage            Reduce bandwidth waste disabling image loading
    -V --version            Print version info
    """)

def version():
    print(f"dyndns-renewal {V}")


def getDriver(headless, noimage):
    locale = "it"
    chrome_options = Options()
    chrome_options.add_argument(f"--lang={locale}")
    chrome_options.add_argument("start-maximized")
    if headless:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
    chrome_prefs = {}
    #chrome_prefs["profile.managed_default_content_settings"] = {"javascript": 2}
    if noimage:
        chrome_prefs["profile.default_content_settings"] = {"images": 2}
        chrome_prefs["profile.managed_default_content_settings"] = {"images": 2}
        chrome_options.add_experimental_option('prefs', chrome_prefs)
    #chrome_options.add_argument("user-data-dir=selenium")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--incognito")

    if not ('raspi' in platform.platform() or 'aarch' in platform.platform()):
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    else:
        driver = webdriver.Chrome(service=Service('/usr/lib/chromium-browser/chromedriver'), options=chrome_options)
    
    sleep(2)
    return driver


def renew_service(driver, con, cur):
    #TODO click su renew service ogni domenica
    try:
        t_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        driver.find_element(By.CSS_SELECTOR, "button.ddns-button.clr-azzurro[value='confirmHost']").click()
        lastConfirm = datetime.datetime.strptime(WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "span#lastConfirm").text, "%d-%m-%Y %H:%M:%S")))
        try:
            logging.info(f'\t{t_now}\tlastConfirm: {lastConfirm}')
            cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (lastConfirm, "Confermed"))
            con.commit()
        except sqlite3.IntegrityError:
            pass
        return True
    except NoSuchElementException:
        logging.error(f'\t{t_now}\tERROR: Confirm button Not Found')
        cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (t_now, "ERROR: Confirm button Not Found"))
        con.commit()
        return False
        

def login(config, con, cur, headless, cookiesless, noimage, c: int=0):
    config.read('./.settings/config.ini')

    driver = getDriver(headless, noimage)
    if not cookiesless:
        try:
            cookies = pickle.load(open("./.settings/dyndns.pkl", "rb"))
        except FileNotFoundError:
            driver.close()
            login(config, con, cur, headless, cookiesless=False, noimage=noimage)
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
            msg = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ddns-div-table.ddns-msg.ddns-error")))
            msg = msg.find_element(By.CSS_SELECTOR, "div.ddns-table-cell.span_10")
            msg = msg.text
            print(msg)
            if 'password' in (msg).lower():
                raise KeyError
            sleep(60)
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
                logging.info(f'\tlastConfirm: {lastConfirm}')
                cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (lastConfirm, "Confermed"))
                con.commit()
            except sqlite3.IntegrityError:
                pass
        except TimeoutException:
            driver.close()
            if cookiesless:
                c = c+1
                return login(config, con, cur, headless, cookiesless=False, noimage=noimage, c=c)
            elif c<2:
                c = c+1
                return login(config, con, cur, headless, cookiesless=True, noimage=noimage, c=c)
            logging.error(f'\tERROR: Confirm page Not Found')
            cur.execute('''INSERT INTO renews(datetime, action) VALUES(?,?);''', (datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "ERROR: Confirm page Not Found"))
            con.commit()            
            raiseExceptions("ERROR: Confirm page Not Found")
            
    #res = cur.execute('''SELECT datetime FROM renews WHERE action=="Confermed" ORDER BY datetime DESC;''')
    #date = datetime.datetime.strptime(res.fetchone()[0], "%Y-%m-%d %H:%M:%S")
    if (datetime.datetime.utcnow()-lastConfirm).days > 20:
        renew_service(driver, con, cur)
    
    return driver


def set_data(config, headless, error=False):
    dir_bcp = os.getcwd()
    try:
        os.mkdir("./.settings")
        config["DEFAULT"] = {}
    except FileExistsError:
        if not os.path.isfile('./.settings/config.ini'):
            config["DEFAULT"] = {}
    os.chdir("./.settings")
    config.read('./config.ini')

    if headless:
        if error:
            print("Nome utente o password errati.")
        user = input("USERNAME: ").strip()
        pwd = input("PASSWORD: ").strip()
        config["DEFAULT"]["user"] = user
        config["DEFAULT"]["pwd"] = pwd
    else:
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


def main(headless, cookiesless, noimage):
    config = configparser.ConfigParser()

    isdb = os.path.isfile('dyndns.db')
    con = sqlite3.connect('dyndns.db')
    cur = con.cursor()
    if not isdb:
        create_db(cur)
    if not os.path.isfile('./.settings/config.ini'):
        set_data(config, headless)
    
    done = False
    while not done:
        try:
            login(config, con, cur, headless, cookiesless, noimage)
            done = True
        except KeyError:
            set_data(config, headless, error=True)


if __name__ == "__main__":
    try:
        try:
            opts, args = getopt.getopt(args=sys.argv[1:], shortopts=shortopts, longopts=longopts)
        except getopt.GetoptError as e:
            print(f"{e}")
            quit()

        headless = False
        cookiesless = False
        noimage = False
        doexit = False

        for opt, arg in opts:
            if opt in ['-h', '--help']:
                help()
                doexit = True
            if opt in ['-l', '--headless']:
                headless = True
            if opt in ['-c', '--cookiesless']:
                cookiesless = True
            if opt in ['-i', '--noimage']:
                noimage = True
            if opt in ['-V', '--version']:
                version()
                doexit = True

        if not headless:
            import tkinter as tk

        if not ('raspi' in platform.platform() or 'aarch' in platform.platform()):
            from webdriver_manager.chrome import ChromeDriverManager

        if not doexit:
            main(headless=headless, cookiesless=cookiesless, noimage=noimage)
    except ModuleNotFoundError as e:
        if 'tkinter' in str(e):
            print(f"[!] {e}\n[!] Use with -l or --headless option!")
        print("[i] Gracefully exit")
        quit()
    except KeyboardInterrupt:
        print("[i] Gracefully exit")
        quit()
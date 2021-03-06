#!/usr/bin/python3
# -*- coding: utf-8 -*-

from imgurpython import ImgurClient
from psaw import PushshiftAPI
from bs4 import BeautifulSoup
from tqdm import tqdm
import urllib.request
import configparser
import requests
import shutil
import math
import time
import sys
import re
import os

help_message = """
Easily download a subreddit's images and videos

Format:
    $ python subreddit_download.py <subreddit> <search term>
    or
    $ python subreddit_download.py <subreddit> <search term> <upvote threshold>

Example:
    $ python subreddit_download.py pics cat

Files are saved to a folder with the same name as the search term.
If you omit the upvote threshold, a praw.ini file will not be required
If you want to download nsfw albums, fill out the imgur.ini file
Thus, images and videos can be gathered without authentication

Use quotes if more than one word
"""
omitted = []

def load_imgur_client(ini_file):
    config = configparser.ConfigParser()
    try:
        config.read(ini_file)
        data = config['imgur']
        return ImgurClient(data['client_id'], data['client_secret']) if '' not in [data['client_id'], data['client_secret']] else None
    except:
        return None

client = load_imgur_client('imgur.ini')

def nsfw_links_from_album(url):
    album_key = url.split('a/')[-1] if '/a/' in url else url.split('gallery/')[-1]
    links = [item.link for item in client.get_album_images(album_key)]
    return links if links else None

def threshold(data, upvote_thresh):
    return [item for item in data if int(item[3]) > upvote_thresh]

def gfycat_source(url):
    soup = BeautifulSoup(requests.get(url).content, 'html.parser')
    try:
        return [item.get('src') for item in list(soup.find_all("source")) if item.get('src') is not None and 'mobile' not in item.get('src') and 'webm' in item.get('src')][0]
    except:
        return None

def imgur_album_source(url):
    album_key = url.split(
        'a/')[-1] if '/a/' in url else url.split('gallery/')[-1]
    soup = BeautifulSoup(requests.get(
        "http://imgur.com/a/" + album_key + "/layout/blog").content, 'html.parser')
    ids = list(set(re.findall(
        '.*?{"hash":"([a-zA-Z0-9]+)".*?"ext":"(\.[a-zA-Z0-9]+)".*?', soup.prettify())))
    links = []
    for item in ids:
        links.append("https://i.imgur.com/" + ''.join(item))
    if len(ids) == 0:
        return url
    return links

def source_url(link):
    if '?' in link:
        link = link.split('?')[0]
    if link.endswith('.gifv'):
        link = link.replace('gifv', 'mp4')
    if any(item in link for item in ['gfycat', 'gifdeliverynetwork', 'redgifs']):
        link = gfycat_source(link)
    elif '/imgur.com' in link and not any(item in link for item in ['/a/', '/gallery/']):
        link = link.replace('imgur', 'i.imgur') + '.jpg'
    elif '/imgur.com' in link and any(item in link for item in ['/a/', '/gallery/']):
        link = imgur_album_source(link) #If it is a nsfw album, it returns itself else a list of link
        if any(item in link for item in ['/a/', '/gallery/']) and client:
            link = nsfw_links_from_album(link)
    elif any(link.endswith(item) for item in ['.gif', '.mp4', '.webm', '.jpg', '.jpeg', '.png']):
        link = link
    return link

def download_images(folder_name, file_names_and_download_links):
    folder_name = os.path.join(os.getcwd(), folder_name)
    if os.path.isdir(folder_name) and not os.listdir(folder_name):
        shutil.rmtree(folder_name)
    os.mkdir(folder_name)

    for i, item in enumerate(tqdm(file_names_and_download_links)):
        if item[1] == None:
            continue
        if item[1] is not None and 'thcf' in item[1]:
            downloaded = False
            for i in range(0, 10):
                try:
                    urllib.request.urlretrieve(
                        item[1], folder_name + '\\' + item[0])
                    downloaded = True
                    break
                except:
                    item[1] = item[1].replace(
                        item[1][item[1].find('thcf')+4], str(i))
                    continue
            if not downloaded:
                omitted.append((item[1], item[0]))
        else:
            try:
                urllib.request.urlretrieve(
                    item[1], folder_name + '\\' + item[0])
            except:
                omitted.append((item[1], item[0]))
                continue
    return folder_name

def search_pushshift(subreddit_name, search_term):
    api = PushshiftAPI()
    psaw_search = list(api.search_submissions(q=search_term, subreddit=subreddit_name,
                                            filter=['id', 'author',
                                                    'title', 'url'],
                                            limit=5000))
    
    return [item for item in psaw_search if 'reddit.com/r/' not in item[4]]

def pushshift_based(results):
    useful_info = [item[2:5] for item in results if None not in item[2:5]]
    return useful_info

def praw_based(results):
    import praw
    r = praw.Reddit('bot1')
    fullnames = []
    for id in [i[2] for i in results]:
        fullnames.append('t3_' + id)

    useful_info = []
    for submission in tqdm(r.info(fullnames), total=len(fullnames)):
        info = [submission.id, submission.title,
                submission.url, submission.score]
        if None not in info:
            useful_info.append(info)
        else:
            continue
    return useful_info

def generate_file_names_and_download_links(pushshift_results, upvote_thresh):
    file_names_and_download_links = []
    if not upvote_thresh:
        information = pushshift_based(pushshift_results)
        print("Gathering " + str(len(information)) + " Source Links")
        for item in tqdm(information):
            source_link = source_url(item[2])
            if isinstance(source_link, list):
                for index, link in enumerate(source_link):
                    #Id - Index . Extension
                    file_names_and_download_links.append([str(item[0]) + '-' + str(index) + '.' +
                                                          str(link).split('.')[-1], link])
            else:
                #Id . Extension
                file_names_and_download_links.append([str(item[0]) + '.' +
                                                      str(source_link).split('.')[-1], source_link])
        print("Downloading " + str(len(file_names_and_download_links)) + " Images")
    else:
        print("Gathering Upvote Data")
        information = threshold(praw_based(pushshift_results), upvote_thresh)
        print("Gathering " + str(len(information)) +
              " Source Links out of a possible " + str(len(pushshift_results)) + " Links")
        for item in tqdm(information):
            source_link = source_url(item[2])
            if isinstance(source_link, list):
                for index, link in enumerate(source_link):
                    #Upvote , Id - Index . Extension
                    file_names_and_download_links.append([str(item[3]) + ',' + str(item[0]) + '-' + str(index) + '.' +
                                                          str(link).split('.')[-1], link])
            else:
                #Upvote , Id . Extension
                file_names_and_download_links.append([str(item[3]) + ',' + str(item[0]) + '.' +
                                                      str(source_link).split('.')[-1], source_link])
        print("Downloading " + str(len(file_names_and_download_links)) +
              " Images out of a possible " + str(len(pushshift_results)) + " Images")
    return file_names_and_download_links

if __name__ == '__main__':
    args = sys.argv[1:]
    upvote_thresh = 0

    if len(args) < 2 or len(args) > 3:
        print(help_message)
        sys.exit()
    if len(args) == 3:
        try:
            upvote_thresh = int(args[2])
        except:
            print("Error: Upvote threshold is not an integer")
            sys.exit()

    print("Searching for" + ' "' + args[1] +
          '" ' + "on " + ', '.join(['r/' + i for i in args[0].split(',')]) + " for images and videos", end='')

    if upvote_thresh:
        print(" with an upvote threshold of " + args[2])

    pushshift_results = []
    for item in args[0].split(','):
        pushshift_results.extend(search_pushshift(item, args[1]))

    if len(pushshift_results) == 0:
        print("No results found. Check to make sure your properly spelled the subreddit name and search term")

    file_names_and_download_links = generate_file_names_and_download_links(
        pushshift_results, upvote_thresh)
    folder = download_images(args[1], file_names_and_download_links)

    if len(omitted):
        print("These links are broken or can't be downloaded: " + str(omitted))

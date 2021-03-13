# Import Packages
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

# import gdown
from zipfile import ZipFile
from joblib import dump, load

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import plot_confusion_matrix

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV

from bs4 import BeautifulSoup
import requests
import re

seed = 0
np.random.seed(seed)

text_tf_idf_vectorizer = load('text_tf_idf_vectorizer.joblib')

text_clf = load('fake_news_classifier.joblib')

# testing on post

# post_text = ' Woah, check out https://www.thegatewaypundit.com/2021/02/ignored-media-dirtbag-joe-biden-says-us-veterans-former-police-officers-fueling-white-supremacism-america/ here'

def isFakeNews(post_text):
    links_in_post = re.findall(r'(https?://\S+)', post_text)

    for link in links_in_post:
        raw_html = requests.get(link).text
        webpage_text = BeautifulSoup(raw_html).text

        webpage_vector = text_tf_idf_vectorizer.transform([webpage_text])

        return text_clf.predict(webpage_vector)[0]

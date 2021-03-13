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

# from bs4 import BeautifulSoup
# import requests
import re

from newspaper import Article

import uuid

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

cred = credentials.Certificate('cs152-project-service-account.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

seed = 0
np.random.seed(seed)

text_tf_idf_vectorizer = load('text_tf_idf_vectorizer.joblib')

text_clf = load('fake_news_classifier.joblib')

'''
Fake News Detection
'''

# post_text = ' Woah, check out https://www.thegatewaypundit.com/2021/02/ignored-media-dirtbag-joe-biden-says-us-veterans-former-police-officers-fueling-white-supremacism-america/ here'
def isFakeNews(post_text):
    links_in_post = re.findall(r'(https?://\S+)', post_text)

    for link in links_in_post:
        # raw_html = requests.get(link).text        
        # webpage_text = BeautifulSoup(raw_html, features="html.parser").text

        article = Article(link)
        article.download()
        article.parse()

        webpage_text = article.text

        webpage_vector = text_tf_idf_vectorizer.transform([webpage_text])

        # print(webpage_text)

        return text_clf.predict(webpage_vector)[0]

'''
Firebase Databse Functions
'''

def add_user(user_name):
    doc_ref = db.collection('users').document(user_name)
    doc_ref.set({
        'name': user_name,
        'reports_for': {
            'correct_reports': 0,
            'incorrect_reports': 0,
            'total_reports': 0,
            'report_weight': 0,
            'report_ids': []
        },
        'reports_against': {
            'correct_reports': 0,
            'incorrect_reports': 0,
            'total_reports': 0,
            'report_weight': 0,
            'report_ids': []
        }
    })

def add_report(post_text, poster_username, reporter_username):
    report_id = str(uuid.uuid4())
    doc_ref = db.collection('reports').document(report_id)
    doc_ref.set({
        'post_text': post_text,
        'poster_username': poster_username,
        'reporter_username': reporter_username,
        'manual_review_validity': None
    })

    add_user_report(reporter_username, report_id, 'reports_for')
    add_user_report(poster_username, report_id, 'reports_against')

    return report_id

def add_user_report(user_name, report_id, report_type):
    doc_ref = db.collection('users').document(user_name)
    doc = doc_ref.get()

    if doc.exists:
        doc = doc.to_dict()

        doc[report_type]['total_reports'] += 1
        doc[report_type]['correct_reports'] = doc[report_type]['correct_reports'] / doc[report_type]['total_reports']
        doc[report_type]['report_ids'].append(report_id)

        doc_ref.set(doc)

def evaluate_report(report_id, validity):
    doc_ref = db.collection('reports').document(report_id)
    doc = doc_ref.get().to_dict()
    
    doc['manual_review_validity'] = validity
    doc_ref.set(doc)

    evaluate_user_report(doc['reporter_username'],validity,'reports_for')
    evaluate_user_report(doc['poster_username'],validity,'reports_against')

def evaluate_user_report(user_name, validity, report_type):
    doc_ref = db.collection('users').document(user_name)
    doc = doc_ref.get()

    if doc.exists:
        doc = doc.to_dict()
        if validity:
            doc[report_type]['correct_reports'] += 1
            doc[report_type]['report_weight'] = doc[report_type]['correct_reports'] / doc[report_type]['total_reports']
        else:
            doc[report_type]['incorrect_reports'] += 1
    
        doc_ref.set(doc)

def get_user_info(user_name):
    return db.collection('users').document(user_name).get().to_dict()

def get_all_users_firebase():
    docs = db.collection('users').stream()

    all_users = []
    for doc in docs:
        all_users.append(doc.id)
    
    return all_users

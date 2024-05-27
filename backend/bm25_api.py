import os
import statistics

from rank_bm25 import BM25Okapi
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer

from threading import Lock

lock = Lock()

corpus_index = None
# Initialize BM25
bm25 = None

# Initialize stemmer and stopwords
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))

# Pre-processing function
def preprocess(text):
    tokens = word_tokenize(text.lower())
    # tokens = [stemmer.stem(token) for token in tokens if token not in stop_words and token.isalpha()]
    tokens = [token for token in tokens if token not in stop_words and token.isalpha()]
    return tokens

def update_corpus():
    global corpus_index
    global bm25
    with lock:
        corpus = []
        corpus_index = {}
        dir = "digests"
        files = os.listdir(dir)
        # doc_manager.client.delete_collection('digests')
        i = 0
        for file in files:
            if not file.startswith("Conversation") and not file.startswith("Note"):
                continue
            title = file.replace(';', ':') # revert conversion for Windows file name rules
            digest = None
            with open(os.path.join(dir, file), encoding='utf-8') as f:
                digest = f.read()
                corpus.append(digest)
                corpus_index[title] = i
                i += 1
                
        # Preprocess the corpus
        processed_corpus = [preprocess(doc) for doc in corpus]
        bm25 = BM25Okapi(processed_corpus, k1=1.5, b=0.75, epsilon=0.25)
    print("bm25 corpus updated")

def standardize(lst):
    mean_val = statistics.mean(lst)
    std_dev = statistics.pstdev(lst)
    if std_dev == 0:
        return [0]*len(lst)
    return [(x - mean_val) / std_dev for x in lst]

def get_norm_bm25_scores(query, doc_id_list):
    with lock:
        query = preprocess(query)[::-1]
        query = list(set(query))
        # Get scores
        doc_index_list = [corpus_index[doc_id] for doc_id in doc_id_list]
        scores = bm25.get_batch_scores(query, doc_index_list)
        norm_scores = standardize(scores)
        print('\n'.join([f"{b}-{a}" for a,b in zip(doc_id_list,norm_scores)]))
        return norm_scores
    
def get_avg_bm25_scores(query, doc_id_list):
    with lock:
        query = preprocess(query)[::-1]
        query = list(set(query))
        # Get scores
        doc_index_list = [corpus_index[doc_id] for doc_id in doc_id_list]
        scores = bm25.get_batch_scores(query, doc_index_list)
        avg_scores = [score/len(query) for score in scores]
        print('\n'.join([f"{b}-{a}" for a,b in zip(doc_id_list,avg_scores)]))
        return avg_scores


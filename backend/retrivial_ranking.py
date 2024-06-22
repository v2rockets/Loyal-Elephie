from datetime import datetime, timedelta
from math import sqrt
from dateparser import parse
from dateparser.search import search_dates

from chroma_doc_manager import doc_manager
from llm_utils import count_token
from bm25_api import get_norm_bm25_scores, get_avg_bm25_scores
from settings import *

class ConversationContext():
    def __init__(self, doc_id, doc_content, score, doc_time=None, match_str=None):
        self.doc_id = doc_id
        if match_str:
            segments = self.split_dialogue(doc_content)
            segments = self.extract_adjacent_segments(segments, match_str.strip())
            self.content = ''.join(segments)
            self.full = False
        else:
            self.content = doc_content
            self.full = True

        self.tokens = count_token(self.content)
        self.value = score/(1+self.tokens/150)
        self.doc_time = doc_time

    def __repr__(self):
        return str(self.__dict__)

def aggregate_scores(associations):
    scores_dict = {}
    for doc_id,_,score in associations:
        if doc_id in scores_dict:
            scores_dict[doc_id] += score
        else:
            scores_dict[doc_id] = score
    return scores_dict

def doc_time_dict(associations):
    time_dict = {}
    for doc_id,doc_time,_ in associations:
        if doc_id not in time_dict:
            time_dict[doc_id] = doc_time
    return time_dict

def search_context(queries):
    query_strings = queries
    query_times = []
    for query_str in queries:
        dates = search_dates(query_str, languages=["en"], settings={"PREFER_DATES_FROM":"past"})
        date = None
        if dates:
            date_str, date = dates[-1]
            query_str = query_str.replace(date_str, "").strip() # remove date from the query string, could be done otherwise
        query_times.append(date)
    query_result = doc_manager.query_by_strings(query_strings)
    def cal_score(dist):
        norm = sqrt(len(queries))
        return (1/(dist+.01)-1)/norm
    
    # associations = [(metadata['doc_id'], metadata['doc_time'], cal_score(distance), sublists[-1]) for sublists in zip(query_result['metadatas'], query_result['distances'], query_times) for metadata, distance in zip(*sublists[:-1])]
    # try to calculate a relevent time closeness multiplier
    all_associations = []
    for i, query_time in enumerate(query_times):
        if query_time:
            associations = [(metadata['doc_id'], metadata['doc_time'], cal_score(distance)) for metadata, distance in zip(query_result['metadatas'][i], query_result['distances'][i])]
            # print(associations)
            days = [abs((datetime.strptime(time_str, "%Y-%m-%d")-query_time).days) for _, time_str, _ in associations]
            # print(days)
            arr2 = [1/(1+d)**2 for d in days]
            avg2 = sum(arr2)/len(arr2)
            k = 1/sqrt(avg2)
            time_corr = [1/(4*k+d)**2 for d in days]
            avg = sum(time_corr)/len(time_corr)
            time_corr = [x/avg for x in time_corr]
            # print(time_corr)
            associations = [(doc_id, doc_time, score*x) for (doc_id, doc_time, score),x in zip(associations,time_corr)]
            # print(associations)
        else:
            associations = [(metadata['doc_id'], metadata['doc_time'], cal_score(distance)) for metadata, distance in zip(query_result['metadatas'][i], query_result['distances'][i])]
        all_associations += associations

    print(all_associations)
    score_dict = aggregate_scores(all_associations)
    time_dict = doc_time_dict(all_associations)
    
    agg_list = sorted(list(score_dict.items()), key=lambda x: x[1], reverse=True) # (doc_id, score)

    full_doc_score = 1.
    # full_doc_ids = [doc_id for doc_id, _, score in associations if score > full_doc_score]

    doc_ids = [i[0] for i in agg_list]
    docs = doc_manager.get_document_by_ids(doc_ids)

    ctx_list = []
    token_limit = RETRIEVAL_TOKEN_LIMIT
    for (doc_id, score), doc in zip(agg_list,docs):
        if not doc: # None means doc is not found
            continue
        ctx = ConversationContext(doc_id, doc, score, time_dict[doc_id])
        print(token_limit, ctx)
        if token_limit > ctx.tokens and (score > full_doc_score or ctx.value > RETRIEVAL_MIN_VALUE):
            ctx_list.append(ctx)
            token_limit -= ctx.tokens
    
    ctx_list = sorted(ctx_list, key=lambda x: x.doc_time)
    return ctx_list

def generate_time_range(date_str:str):
    print("timed_query: ", date_str)
    start_date = parse(date_str, languages=["en"], settings={"PREFER_DATES_FROM":"past", "PREFER_MONTH_OF_YEAR": "first", 'PREFER_DAY_OF_MONTH': 'first'})
    end_date = parse(date_str, languages=["en"], settings={"PREFER_DATES_FROM":"past", "PREFER_MONTH_OF_YEAR": "last", 'PREFER_DAY_OF_MONTH': 'last'})
    if "month" in date_str.lower() and end_date.toordinal() - start_date.toordinal() < 15: # parsed to point, recover
        start_date = start_date - timedelta(days=30)
        end_date = end_date + timedelta(days=30)
    if "week" in date_str.lower() and end_date.toordinal() - start_date.toordinal() < 4: # parsed to point, recover
        start_date = start_date - timedelta(days=7)
        end_date = end_date + timedelta(days=7)
    return start_date, end_date

def cal_score(dist, len_query):
    norm = sqrt(len_query)
    return (1/(dist+.01)-1)/norm

# adjust for overall false-positive
def get_adjust_factor(double_associations, n_required):
    rectify_factor = 0.5
    spare_asso = double_associations[n_required:]
    if not spare_asso:
        return 1
    n_weight = len(spare_asso)
    # avg = sum([x[2] for x in spare_asso])/n_weight
    last = double_associations[n_required + n_weight - 1][2]
    return (1/last-1)*(rectify_factor*n_weight/n_required) + 1

def get_all_associations(queries, n_choices=RETRIEVAL_NUM_CHOICES):
    query_strings = queries
    query_result = doc_manager.query_by_strings(query_strings, n_results=n_choices*2)
    print(query_result)
    all_associations = []
    for i, query_str in enumerate(query_strings):
        dates = search_dates(query_str, languages=["en"], settings={"PREFER_DATES_FROM":"past"})
        if dates:
            time_factor = 1.5
            double_associations = [(metadata['doc_id'], metadata['doc_time'], distance) for metadata, distance in zip(query_result['metadatas'][i], query_result['distances'][i])]
            adj_factor = get_adjust_factor(double_associations, n_choices)
            print("adj_factor: ", adj_factor)
            associations = [(x,y,cal_score(z*adj_factor*time_factor, len(queries))) for x,y,z in double_associations[:n_choices//2]] # first half is still original results with distance penalty
            date_str, _ = dates[-1]
            start_date, end_date = generate_time_range(date_str)
            new_query_str = query_str.replace(date_str, "")
            new_query_result = doc_manager.query_by_strings_with_time_range([new_query_str], n_results=n_choices*2, start_time=start_date, end_time=end_date)
            new_double_associations = [(metadata['doc_id'], metadata['doc_time'], distance) for metadata, distance in zip(new_query_result['metadatas'][0], new_query_result['distances'][0])]
            new_adj_factor = get_adjust_factor(new_double_associations, n_choices)
            print("new_adj_factor: ", new_adj_factor)
            new_associations = [(x,y,cal_score(z*adj_factor/time_factor, len(queries))) for x,y,z in new_double_associations[:n_choices//2]]
            associations += new_associations
        else:
            double_associations = [(metadata['doc_id'], metadata['doc_time'], distance) for metadata, distance in zip(query_result['metadatas'][i], query_result['distances'][i])]
            adj_factor = get_adjust_factor(double_associations, n_choices)
            print("adj_factor: ", adj_factor)
            associations = [(x,y,cal_score(z*adj_factor, len(queries))) for x,y,z in double_associations[:n_choices]]
        all_associations += associations

    # print(all_associations)
    return all_associations

def search_context_with_time(queries):
    all_associations = get_all_associations(queries)
    score_dict = aggregate_scores(all_associations)
    time_dict = doc_time_dict(all_associations)
    
    agg_list = sorted(list(score_dict.items()), key=lambda x: x[1], reverse=True) # (doc_id, score)

    full_doc_score = 1.
    # full_doc_ids = [doc_id for doc_id, _, score in associations if score > full_doc_score]

    doc_ids = [i[0] for i in agg_list]
    docs = doc_manager.get_document_by_ids(doc_ids)
    bm25_scores = get_avg_bm25_scores(' '.join(queries), doc_ids)
    # min_bm25_scores = min(bm25_scores)

    ctx_list = []
    token_limit = RETRIEVAL_TOKEN_LIMIT
    for (doc_id, score),doc,bm25_score in zip(agg_list,docs,bm25_scores):
        if not doc: # None means doc is not found
            continue
        # score += (bm25_score - min_bm25_scores)/10
        score += bm25_score*BM25_WEIGHT
        ctx = ConversationContext(doc_id, doc, score, time_dict[doc_id])
        print(token_limit, ctx)
        if token_limit > ctx.tokens and (score > full_doc_score or ctx.value > RETRIEVAL_MIN_VALUE):
            ctx_list.append(ctx)
            token_limit -= ctx.tokens
    
    ctx_list = sorted(ctx_list, key=lambda x: x.doc_time)
    return ctx_list

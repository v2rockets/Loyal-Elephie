import os
import chromadb
import datetime
import threading
from chromadb import EmbeddingFunction
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from llm_utils import get_embeddings

ROOT_FOLDER = 'digests'

class EmbeddingFunction(EmbeddingFunction):
    def __call__(self, input):
        return get_embeddings(input)

class DocumentFolder():
    def __init__(self, dir) -> None:
        self.dir = dir
        if not os.path.exists(dir):
            os.mkdir(dir)

    def save(self, doc_id, string):
        doc_name = doc_id.replace(':', ';')
        with open(os.path.join(self.dir,doc_name), "w+", encoding='utf-8') as f:
            f.write(string)

    def load(self, doc_id):
        doc_name = doc_id.replace(':', ';')
        with open(os.path.join(self.dir,doc_name), encoding='utf-8') as f:
            s = f.read()
            return s

    def delete(self, doc_id):
        doc_name = doc_id.replace(':', ';')
        path = os.path.join(ROOT_FOLDER,doc_name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    
class ChromaDocManager:
    def __init__(self):
        self.lock = threading.Lock()
        # Initialize a persistent Chroma client
        self.client = chromadb.PersistentClient(path=f'./{ROOT_FOLDER}/chroma', settings=Settings(anonymized_telemetry=False)) # this will not refresh on file change
        self.collection = self.client.get_or_create_collection(name='digests', embedding_function=EmbeddingFunction())
        self.folder = DocumentFolder(ROOT_FOLDER)

    # Define a function to add documents to the Chroma database
    def _add_index(self, document: str, doc_id: str, other_meta=None, chunk_size=100, chunk_overlap=0):
        assert ';' not in doc_id
        # Split the document into chunks using the RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.split_text(document)
        # Add each chunk to ChromaDB with associated doc_id and its index
        ids = [f"{doc_id}_{i}" for i, _ in enumerate(chunks)]
        # embed_chunks = get_embeddings(chunks)
        doc_metadata = {"doc_id": doc_id}
        if other_meta:
            doc_metadata.update(other_meta)
        if not "doc_time" in doc_metadata:
            doc_metadata["doc_time"] = datetime.datetime.now().strftime("%Y-%m-%d")
        self.collection.upsert(documents=chunks, ids=ids, metadatas=[doc_metadata]*len(chunks))
        
    def add_document(self, document: str, doc_id: str, **kwargs):
        with self.lock:
            self._remove_index_by_doc_id(doc_id)
            self._add_index(document, doc_id, **kwargs)
            self.folder.save(doc_id, document)

    def query_by_strings(self, strings, n_results):
        with self.lock:
            # Split the string into chunks for embedding
            res = self.collection.query(
                query_texts=strings,
                n_results=n_results,
                include = [ "documents", "metadatas", "distances" ]
            )
            return res
        
    def query_by_strings_with_time_range(self, strings, n_results, start_time, end_time):
        with self.lock:
            start_time_str = start_time.strftime("%Y-%m-%d")
            end_time_str = end_time.strftime("%Y-%m-%d")
            print("search range: ", start_time_str, end_time_str)
            # Split the string into chunks for embedding
            res = self.collection.query(
                query_texts=strings,
                n_results=n_results,
                include = [ "documents", "metadatas", "distances" ],
                where = {"$and":[{"doc_time":{"$gte": start_time_str}}, {"doc_time":{"$lte": end_time_str}}]}
            )
            return res

    def query_by_doc_id(self, doc_id):
        with self.lock:
            res = self.collection.get(
                where = {"doc_id":doc_id},
                include = [ "documents", "metadatas" ]
            )
            return res
        
    def _query_by_name(self, doc_name):
        res = self.collection.get(
            where = {"doc_name":doc_name},
            include = [ "metadatas" ]
        )
        return res

    def query_all(self):
        with self.lock:
            return self.collection.get(include = [ "documents", "metadatas" ])
    
    def _remove_index_by_doc_id(self, doc_id: str):
        self.collection.delete(where={"doc_id":doc_id})

    def remove_document(self, doc_id: str):
        with self.lock:
            self._remove_index_by_doc_id(doc_id)
            self.folder.delete(doc_id)

    def remove_document_by_name(self, doc_name: str):
        with self.lock:
            res = self._query_by_name(doc_name)
            print(res["metadatas"])
            if res["metadatas"]:
                ids = set([x['doc_id'] for x in res["metadatas"]])
                print("to remove: ", ids)
                for doc_id in ids:
                    self._remove_index_by_doc_id(doc_id)
                    self.folder.delete(doc_id)

    def get_document_by_ids(self, doc_ids):
        with self.lock:
            return [self.folder.load(doc_id) for doc_id in doc_ids]

    # def update_document(self, document: str, doc_id: str):
    #     # Update the document in ChromaDB by first removing and then adding the new chunks
    #     self.remove_document(doc_id)
    #     self.add_document(document, doc_id)
        
doc_manager = ChromaDocManager()

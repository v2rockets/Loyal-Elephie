import os
import chromadb
import datetime
import threading
from chromadb import EmbeddingFunction
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from llm_utils import get_embeddings

ROOT_FOLDER = 'digests'

# ---------------------------------------------------------------------------
# Monkey patch ChromaDB's validate_where function to support string comparison
# ---------------------------------------------------------------------------
# ChromaDB doesn't support string comparison for the $gte/$lte operators by default.
# This code overrides the default validate_where function to add this functionality
# without modifying the original ChromaDB source code.
def custom_validate_where(where: dict) -> dict:
    """
    Custom validation function to allow string comparison for the $gte operator.
    """
    if not isinstance(where, dict):
        raise ValueError(f"Expected where to be a dict, got {where}")
    if len(where) != 1:
        raise ValueError(f"Expected where to have exactly one operator, got {where}")
    for key, value in where.items():
        if not isinstance(key, str):
            raise ValueError(f"Expected where key to be a str, got {key}")
        if (
            key != "$and"
            and key != "$or"
            and key != "$in"
            and key != "$nin"
            and not isinstance(value, (str, int, float, dict))
        ):
            raise ValueError(
                f"Expected where value to be a str, int, float, or operator expression, got {value}"
            )
        if key == "$and" or key == "$or":
            if not isinstance(value, list):
                raise ValueError(
                    f"Expected where value for $and or $or to be a list of where expressions, got {value}"
                )
            if len(value) <= 1:
                raise ValueError(
                    f"Expected where value for $and or $or to be a list with at least two where expressions, got {value}"
                )
            for where_expression in value:
                custom_validate_where(where_expression)
        # Value is an operator expression
        if isinstance(value, dict):
            # Ensure there is only one operator
            if len(value) != 1:
                raise ValueError(
                    f"Expected operator expression to have exactly one operator, got {value}"
                )

            for operator, operand in value.items():
                # Allow strings for gt, gte, lt, lte
                if operator in ["$gt", "$gte", "$lt", "$lte"]:
                    if not isinstance(operand, (str, int, float)):
                        raise ValueError(
                            f"Expected operand value to be a str, int, or float for operator {operator}, got {operand}"
                        )
                if operator in ["$in", "$nin"]:
                    if not isinstance(operand, list):
                        raise ValueError(
                            f"Expected operand value to be a list for operator {operator}, got {operand}"
                        )
                if operator not in [
                    "$gt",
                    "$gte",
                    "$lt",
                    "$lte",
                    "$ne",
                    "$eq",
                    "$in",
                    "$nin",
                ]:
                    raise ValueError(
                        f"Expected where operator to be one of $gt, $gte, $lt, $lte, $ne, $eq, $in, $nin, "
                        f"got {operator}"
                    )

                if not isinstance(operand, (str, int, float, list)):
                    raise ValueError(
                        f"Expected where operand value to be a str, int, float, or list of those types, got {operand}"
                    )
                if isinstance(operand, list) and (
                    len(operand) == 0
                    or not all(isinstance(x, type(operand[0])) for x in operand)
                ):
                    raise ValueError(
                        f"Expected where operand value to be a non-empty list, and all values to be of the same type "
                        f"got {operand}"
                    )
    return where

chromadb.api.types.validate_where = custom_validate_where
# ---------------------------------------------------------------------------

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

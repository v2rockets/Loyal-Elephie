from openai import OpenAI
from langchain.text_splitter import MarkdownHeaderTextSplitter
import tiktoken

from settings import *

client_embed = OpenAI(base_url = EMBEDDING_BASE_URL, api_key = EMBEDDING_API_KEY)
client = OpenAI(base_url = CHAT_BASE_URL, api_key = CHAT_API_KEY)

def get_embeddings(chunks):
    data = client_embed.embeddings.create(input=chunks, model=EMBEDDING_MODEL_NAME).data
    return [d.embedding for d in data]

def chat(messages:list[dict]):
    response = client.chat.completions.create(
        model=CHAT_MODEL_NAME,
        messages=messages,
        max_tokens=CHAT_MAX_TOKEN
    )
    return response.choices[0].message.content

def simplify_markdown_headers(page_content, current_nesting_level):
    # Split the content into lines for processing
    lines = page_content.split('\n')

    # Process each line to adjust header levels
    simplified_lines = []
    for line in lines:
        # Check if the line starts with markdown header syntax
        if line.startswith('#'):
            # Count the number of '#' to determine the original level
            header_level = line.count('#')

            # Calculate the new header level
            new_header_level = header_level - current_nesting_level + 1

            # Ensure the new header level is at least 1
            new_header_level = max(new_header_level, 1)

            # Replace the original header syntax with the new level
            new_header = '#' * new_header_level + ' ' + line.lstrip('#').lstrip()
            simplified_lines.append(new_header)
        else:
            # If it's not a header, keep the line as is
            simplified_lines.append(line)

    # Join the lines back into a single string
    simplified_content = '\n'.join(simplified_lines)
    return simplified_content


# This function will try to digest a markdown file into multiple docs based on headers
def digest_markdown(title, path):
    headers = [
        ("#", "header1"),
        ("##", "header2"),
        ("###", "header3"),
    ]
    parent_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
    with open(path, encoding='utf-8') as f:
        s = f.read()
        docs = parent_splitter.split_text(s)
    digests = []
    for doc in docs:
        headers = ""
        headers += title
        level = 0
        if 'header1' in doc.metadata:
            headers += " > " + doc.metadata['header1'].strip()
            level = 1
        if 'header2' in doc.metadata:
            headers += " > " + doc.metadata['header2'].strip()
            level = 2
        if 'header3' in doc.metadata:
            headers += " > " + doc.metadata['header3'].strip()
            level = 3
        page_content = simplify_markdown_headers(doc.page_content.strip(), level)
        content = f"---Begin Note---\nHeaders: {headers}\n{page_content}\n---End Note---"
        summary = chat([
            {"role": "system", "content": SUMMARY_NOTE_PROMPT},
            {"role": "user", "content": content}]
        )
        # digest = f"# {headers}\n{summary}"
        digests.append((headers, summary))
    return digests

def digest_simple(title, path):
    with open(path, encoding='utf-8') as f:
        s = f.read()
        tag = ""
        if s.startswith('#'): # tagged doc
            tag, s = s.split('\n',1)
            tag = tag.lstrip('#').strip()
        text = f"---{title}---\n{s}"
        summary = chat([
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": text}]).strip()
        print(">>>", tag)
        return summary, tag
    
def count_token(input_str):
    encoding = tiktoken.get_encoding("cl100k_base")
    if type(input_str) == dict:
        input_str = f"role: {input_str['role']}, content: {input_str['content']}"
    length = len(encoding.encode(input_str))
    return length

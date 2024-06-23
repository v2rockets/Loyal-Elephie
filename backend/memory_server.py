import json
import re
from typing import List, Optional, Literal, Union, Iterator, Dict
import datetime
import os
from enum import Enum
import jwt

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import llama_types as llama_cpp
from llm_utils import client
from retrivial_ranking import search_context, search_context_with_time
from settings import *

app = FastAPI(
    title="Memory Server",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

server_state = {"last_use":None}
latest_chat_time = None
latest_chat_message = None

MAX_NUM_QUERY = 3

prompt_no_action = '''No valid actions taken. You need to use SEARCH or REPLY block.'''

prompt_last_warning = '''You need to answer back to the user immediately with the REPLY block otherwise your task is failed.'''

prompt_no_result = '''No context found for the latest search.'''


def serialize_chat_chunk(chunk):
    return {
        'id': chunk.id,
        'object': chunk.object,
        'created': chunk.created,
        'model': chunk.model,
        'choices': [
            {
                'index': choice.index,
                'finish_reason': choice.finish_reason,
                'delta': {
                    'content': choice.delta.content,
                    'function_call': choice.delta.function_call,
                    'role': choice.delta.role,
                    'tool_calls': choice.delta.tool_calls
                },
                'logprobs': choice.logprobs
            } for choice in chunk.choices
        ]
    }

class ChatCompletionRequestMessage(BaseModel):
    role: Union[Literal["system"], Literal["user"], Literal["assistant"], Literal["function"]]
    content: str
    user: Optional[str] = None

class CreateChatCompletionRequest(BaseModel):
    model: Optional[str]
    messages: List[llama_cpp.ChatCompletionRequestMessage]
    functions: Optional[List[llama_cpp.ChatCompletionFunction]] = Field(
        default=None,
        description="A list of functions to apply to the generated completions.",
    )
    function_call: Optional[llama_cpp.ChatCompletionRequestFunctionCall] = Field(
        default=None,
        description="A function to apply to the generated completions.",
    )
    temperature: Optional[float] = 0.1
    top_p: Optional[float] = 0.95
    stream: Optional[bool] = False
    stop: Optional[List[str]] = []
    max_tokens: Optional[int] = 128

    # ignored or currently unsupported
    model: Optional[str] = Field(None)
    n: Optional[int] = 1
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, float]] = Field(None)
    user: Optional[str] = Field(None)

    # llama.cpp specific parameters
    repeat_penalty: Optional[float] = 1.1
    response_format: Optional[llama_cpp.ChatCompletionRequestResponseFormat] = Field(
        default='json',
    )

    class Config:
        schema_extra = {
            "example": {
                "messages": [
                    ChatCompletionRequestMessage(
                        role="system", content="You are a helpful assistant."
                    ),
                    ChatCompletionRequestMessage(
                        role="user", content="What is the capital of France?"
                    ),
                ]
            }
        }

class OutputState(Enum):
    Input = 0
    Reply = 1
    Search = 2
    Finish = 3
    ToSearch = 4
    ToReply = 5
        
def generate_system_message(content, use_system = MULTILPLE_SYSTEM_PROMPTS):
    if use_system:
        return {"role":"system", "content": content}
    else:
        return {"role":"user", "content": "system:\n" + content}

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

with open('language_presets.json', 'r', encoding='utf-8') as file:
    lang_presets = json.load(file)

async def get_api_key(api_key_header: str = Depends(api_key_header)):
    try:
        token = api_key_header.split(' ')[1]
        decoded = jwt.decode(token, "shared_key", algorithms=['HS256'])
        user = decoded["username"]
        return user
    except:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=403, 
            detail="Could not validate API Key"
        )
    
# TODO find other solutions
response_start = False
@app.post(
    "/v1/chat/completions",
    response_model=llama_cpp.ChatCompletion,
)
async def create_chat_completion(
        request: CreateChatCompletionRequest, user: str = Depends(get_api_key)
) -> Union[llama_cpp.ChatCompletion, EventSourceResponse]:
    print(f"call from {user}")
    kwargs = request.dict(exclude={"model", "n", "presence_penalty", "frequency_penalty", "logit_bias", "user", })
    # print("debug: ", json.dumps(kwargs).encode('utf-8').decode('unicode_escape'))
    
    messages = kwargs['messages']
    last_chat = messages[-1]['content']
    print('### USER: ', last_chat)


    # A simple solution: judge if the conversation is new by comparing the first user message
    global latest_chat_message,latest_chat_time, server_state
    time_now = datetime.datetime.now()
    server_state["last_use"] = time_now
    if latest_chat_message and messages[1]['content'] == latest_chat_message:
        print("Continued conversation")
    else:
        latest_chat_message = messages[1]['content']
        latest_chat_time = time_now.strftime('%Y-%m-%d %H:%M:%S')
    
    if '*SAVE*' in last_chat:
        try:
            title = 'Conversation on ' + latest_chat_time
            filename = title.replace(':',';') + '.md'
            tag = last_chat.lstrip().replace("*SAVE*", "", 1).strip()
            formatted_conversation = ""
            for message in messages[:-1]:
                if message['role'] == 'user':
                    formatted_conversation += f"{message['role'].upper()}: {message['content'].strip()}\n"
                elif message['role'] == 'assistant':
                    content = message['content'].split('\n###')[0] # clear reference text
                    formatted_conversation += f"{message['role'].upper()}: {content.strip()}\n"
            with open(os.path.join(CHAT_PATH, filename), "w+", encoding='utf-8') as f:
                if len(tag):
                    f.write(f"# {tag}\n")
                f.write(formatted_conversation)
            print("saved to: ", filename)
        except:
            return EventSourceResponse(
                    single_message_generator("Conversation saving failed."),
            )

        return EventSourceResponse(
                    single_message_generator("Conversation saved successfully."),
        )
    
    state = OutputState.Input
    all_context_list = []

    prompt = AGENT_PROMPT.replace("{CURRENT_TIME}", latest_chat_time).replace("{NICK_NAME}", NICK_NAME)
    prompt = prompt.replace("{LANGUAGE_PREFERENCE}", "" if LANGUAGE_PREFERENCE=="English" else f"\n**Your default langauge for search queries and reply contents is {LANGUAGE_PREFERENCE}.**")
    print(">>>", LANGUAGE_PREFERENCE, prompt)
    # Prepare formmating
    new_messages = [{'role':'system', 'content': prompt}]
    
    language = LANGUAGE_PREFERENCE
    # add one-shot prompt
    new_messages += [
        {'role':'user','content': lang_presets["languages"][language]["user_message"]},
        {'role':'assistant','content':f'<THINK>{lang_presets["languages"][language]["think_message"].format(NICK_NAME=NICK_NAME)}</THINK>'},
        {'role':'assistant','content':f'<SEARCH>\n{lang_presets["languages"][language]["search_query"].format(NICK_NAME=NICK_NAME)}</SEARCH>'},
        generate_system_message(f'---begin search result---\n<context_1 title="{lang_presets["languages"][language]["context_title"]}">\n{lang_presets["languages"][language]["context_content"].format(NICK_NAME=NICK_NAME)}\n---end search result---'),
        {'role':'assistant','content':f'<REPLY>{lang_presets["languages"][language]["reply_message"].format(NICK_NAME=NICK_NAME)}</REPLY>'},
    ]
    
    for i in range(1, len(messages)):
        if messages[i]['role'] == 'assistant':
            contents = messages[i]['content'].split('\n###',1)
            content = contents[0]
            if len(contents) > 1:
                # reference = contents[1]
                new_messages.append(generate_system_message("Your have searched the memory but the result content is hidden. If you need the details include relevant topics in SEARCH block again."))
            new_messages.append({'role':'assistant', 'content': f"<REPLY>{content}</REPLY>"})
        else:
            new_messages.append(messages[i].copy())

    
    def generate_ref(doc_id):
        if doc_id.startswith("Conversation on"):
            return f"[{doc_id}]({CHAT_URL + doc_id.replace(':',';')})"
        elif doc_id.startswith("Note of "):
            headers = doc_id.replace('Note of ', '', 1)
            return f"[{headers}]({NOTE_URL + headers.split(' > ')[0].replace(':',';')})"
        else:
            return f"[null]({doc_id})"

    def format_context(i, ctx):
        if ctx.doc_id.startswith("Conversation on"):
            return f"<context {i+1} title={ctx.doc_id}/>\n{ctx.content}\n"
        elif ctx.doc_id.startswith("Note of "):
            return f"<context {i+1} title={ctx.doc_id} modified={ctx.doc_time}/>\n{ctx.content}\n"
        else:
            return ""
        
    def stream_output(
            chat_chunks: Iterator[llama_cpp.ChatCompletionChunk], extra_text: str
    ):
        nonlocal state, all_context_list
        for chat_chunk in chat_chunks:
            if state == OutputState.ToReply:
                state = OutputState.Reply
                print('### ASSISTANT: ', end='')
                if extra_text:
                    chat_chunk.choices[0].delta.content = extra_text + chat_chunk.choices[0].delta.content
            s = chat_chunk.choices[0].delta.content
            chat_chunk.choices[0].finish_reason = None # avoid "stop" causing ref_text not received
            print(s,end='')
            yield dict(data=json.dumps(serialize_chat_chunk(chat_chunk)))
        print('\n')

        if state == OutputState.Reply:
                state = OutputState.Finish
        
        if all_context_list:
            ref_text = "\n###\n" + '\n'.join([generate_ref(doc_id) for doc_id in all_context_list])
            # print(">>>added ref: ", ref_text)
            yield dict(data=json.dumps(getChatCompetionChunk(ref_text)))
        yield dict(data="[DONE]")

    if request.stream:
        chain_length = 0
        while(state!=OutputState.Finish):
            print(new_messages)
            if chain_length > 3:
                print("retry too many times")
                return EventSourceResponse(
                    single_message_generator("Failed to generate valid response, please try again."),
                )
            elif chain_length == 3:
                new_messages.append(generate_system_message(prompt_last_warning))

            if state==OutputState.Input:
                chain_length += 1
                completion_or_chunks = client.chat.completions.create(
                    model=CHAT_MODEL_NAME,
                    messages=new_messages,
                    temperature=0.1,
                    max_tokens=kwargs['max_tokens'],
                    stream=True,  # this time, we set stream=True
                    stop=["\n###", "</SEARCH>", "</REPLY>"],
                )

        
            accumulated_content = ''
            
            def get_stream(chat_chunks:Iterator[llama_cpp.ChatCompletionChunk]):
                nonlocal accumulated_content
                output_state = OutputState.Input
                for chat_chunk in chat_chunks:
                    s = chat_chunk.choices[0].delta.content
                    print(s, end='')
                    accumulated_content += s
                    if output_state == OutputState.Input:
                        if '<SEARCH>' in accumulated_content:
                            output_state = OutputState.Search
                        elif '<REPLY>' in accumulated_content:
                            output_state = OutputState.ToReply
                            return output_state
                if output_state ==  OutputState.Search:
                    return OutputState.ToSearch
                return output_state
            
            state = get_stream(completion_or_chunks)
            monologue = extract_tagged_content(accumulated_content, 'THINK').strip()
            if len(monologue):
                new_messages.append({"role":"assistant", "content": f"<THINK>{monologue}</THINK>"})

            if state == OutputState.ToSearch:
                search_string = accumulated_content.split('<SEARCH>', 1)[-1].strip()
                if len(search_string):
                    queries = arrange_query_string(search_string)
                    print("queries:", queries)
                    new_messages.append({"role":"assistant", "content": f"<SEARCH>{search_string}</SEARCH>"})
                    context_list = search_context_with_time(queries)
                    if context_list:
                        search_result = '<br/>\n'.join([format_context(i, ctx) for i, ctx in enumerate(context_list)])
                        all_context_list += [ctx.doc_id for ctx in context_list]
                    else:
                        search_result = prompt_no_result
                    new_messages.append(generate_system_message(f"---begin search result---\n{search_result}\n---end search result---"))
                    state = OutputState.Input

            elif state == OutputState.ToReply:
                chunks: Iterator[llama_cpp.ChatCompletionChunk] = completion_or_chunks  # type: ignore
                extra_text = accumulated_content.split('<REPLY>',1)[-1]
                return EventSourceResponse(
                    stream_output(chunks, extra_text),
                )
            
            elif state == OutputState.Reply:
                state = OutputState.Finish
            else:
                if not len(monologue):
                    new_messages.append(generate_system_message(prompt_no_action))
                state = OutputState.Input
    else:
        completion: llama_cpp.ChatCompletion = completion_or_chunks  # type: ignore
        return completion

def extract_tagged_content(text, tag):
    # Construct the regular expression pattern dynamically based on the tag
    pattern = rf'<{tag}>(.*?)</{tag}>'
    # Find all matches and strip each content, then join them with newline characters
    tagged_contents = [match.strip() for match in re.findall(pattern, text, re.DOTALL)]
    return "\n".join(tagged_contents) if tagged_contents else ""

def arrange_query_string(search_text):
    n_queries = 0
    queries = []
    for q in search_text.split('\n'):
        query_str = q.strip()
        if not len(query_str) or n_queries > MAX_NUM_QUERY:
            break
        queries.append(query_str)
        n_queries += 1
    return queries

def getChatCompetionChunk(message, finish_reason=None):
    response: llama_cpp.ChatCompletionChunk = {
        "id": "chatcmpl-7eijdlu4SYVIczkFfRVZMd7tZEURH",
        "model": "gpt-3.5-turbo",
        "object": "chat.completion.chunk",
        "created": 0,
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": message,
                    "role": "system"
                },
                "finish_reason": finish_reason
            }
        ]
    }
    return response

async def single_message_generator(message):
    response = getChatCompetionChunk(message, finish_reason='stop')
    yield {"data": json.dumps(response)}

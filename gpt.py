"""
   Class for interacting with the OpenAI API endpoints.
   1. embedd_text: for embedding text and creat a vector
   2. json_gpt: using the gpt-4o model provided by OpenAI and generate a JSON formatted response

"""

import openai
import json
import os

class GPT:
  def __init__(self):
    open_key=self._load_key('../keys.json')
    self.key=open_key

  #load keys from file
  def _load_key(self, key_file):
    try:
      with open(key_file, "r") as f:
        data = json.load(f)
        return data.get("key")
    except Exception as e:
      print(f"An unexpected error occurred: {e}")
      return None

  #embedding
  def embedd_text(self,text):
    openai.api_key=self.key
    res=openai.embeddings.create( model="text-embedding-3-small", input=text)
    return res.data[0].embedding
  def json_gpt(self,message,tokens=4096):
    openai.api_key=self.key
    res = openai.chat.completions.create(model="gpt-4o",messages=message,temperature=0.4,response_format={"type": "json_object"},max_tokens=tokens)
    return res.choices[0].message.content

  def gpt_3(self, text, tokens=500):
    openai.api_key=self.key
    res=openai.chat.completions.create(engine="gpt-3.5-turbo-instruct",prompt=text,temperature=0.3,max_tokens=tokens)
    return res.choices[0].text

  def gpt_4o(self, message, tokens=500):
    openai.api_key=self.key
    res = openai.chat.completions.create(model="gpt-4o",messages=message,temperature=0.5,max_tokens=tokens)
    return res.choices[0].message

  def file_processor(self, instruction, text):
    #method for processing files using code interpreter
    openai.api_key=self.key
    assistant = openai.beta.assistants.create(
      instructions=instruction,
      model="gpt-4o",
      tools=[{"type": "code_interpreter"}],
    )

    thread = openai.beta.threads.create()
    message = openai.beta.threads.messages.create(
      thread_id=thread.id,
      role="user",
      content=text
    )
    run = openai.beta.threads.runs.create_and_poll(
      thread_id=thread.id,
      assistant_id=assistant.id,
      instructions=instruction
    )

    if run.status == 'completed':
      messages = openai.beta.threads.messages.list(thread_id=thread.id)
      print(messages)
    else:
      print(run.status)

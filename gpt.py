"""
   Class for interacting with the OpenAI API endpoints.
   1. embedd_text: for embedding text and creat a vector
   2. json_gpt: using the gpt-4o model provided by OpenAI and generate a JSON formatted response

"""

import openai

class GPT:
  def __init__(self):
    self.key="key"

  #embedding
  def embedd_text(self,text):
    openai.api_key=self.key
    res=openai.Embedding.create( model="text-embedding-3-small", input=text)
    return res.data[0].embedding
  def json_gpt(self,message,tokens=4096):
    openai.api_key=self.key
    res = openai.ChatCompletion.create(model="gpt-4o",messages=message,temperature=0.4,response_format={"type": "json_object"},max_tokens=tokens)
    return res.choices[0]['message']['content']

  def gpt_3(self, text, tokens=500):
    openai.api_key=self.key
    res=openai.Completion.create(engine="gpt-3.5-turbo-instruct",prompt=text,temperature=0.3,max_tokens=tokens)
    return res.choices[0].text

  def gpt_4o(self, message, tokens=500):
    openai.api_key=self.key
    res = openai.ChatCompletion.create(model="gpt-4o",messages=message,temperature=0.5,max_tokens=tokens)
    return res.choices[0]['message']['content']
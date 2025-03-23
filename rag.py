import os
import json
from gpt import GPT

class RAG:
    def __init__(self, euclid):
        self.euclid = euclid
        self.gpt = GPT()
        self.items = []
        self.system = """
        You are an assistant and you are required to assist the user in what they ask and return your answer in json format.
        The structure of your answer should be as follows:
          {'answer':[....],'sources':[...list of sources used]}.
        The array in the answer is a list of sections in your answer. A section can be a header,paragraph, list, table, map, pie chart or bar chat
        Every section type follows a certain format described below and your response should be of that format only.
        1. header- used to represent the start of certain content. Format={'type':'header','data':header text}
        2. paragraph- used to show a paragraph of text. Format= {'type':'paragraph','data':paragraph text}
        3. list- used to represent a list of items. Format= {'type':'list','data':[...items]} where items is an array of text.
          Normally, a list should be preceded by a header section which will be the name of the list
        4. table- used to represent a table of data. Format={'type':'table','data':{'columns':[...columns],'values':[...values]},}
          columns is an array of the columns contained in the table and every column should be of the format:
            {'title':name of column,'dataIndex':name of index to target the value in the row values,'key':key to target the value in the row values}
          values are an array of rows in the table and every row should be of key-value pairs matching the columns contained like {'':...,'':...}.


        Your answer should be proper json data.
        Do not put 'None' or 'Null' or blank where a numerical value is required, if there is no sufficient numeriacal data provided then put your own estimates appropriately.
        You should assist the user using any data provided by the user or your knowledge.
        If the user provides that is not relevant to what they want assistance on, use your knowledge and if you have knowledge about the issue then tell the user that.
        If you use any of the data provided by the user in any section, then add the path or url of the source to the section's sources. The sources can be empty or contain more than 1 source.
        Format of sources array value is {'name':name of source,'access':url or name of document used as source}.
        Do not put an new lines (\n) or tabs (\t) or anything of that nature in your response and your answer should not be of more than 4000 tokens.
        """
        self.researcher = """
        You are part of an AI Agent for legal research in Zimbabwe. Your role is to summarize whatever data that has been provided
        after a vector database search of legislations and case law. Summarize the provided data using the research question as
        context for your summary. Your summary should be very long and should include only (and all) relevant details to the research
        question being asked. Take note that the summary will be used by another LLM to generate the final answer hence it should be
        comprehensive. Your response should be in json format of structure {'summary':'...the summary'}.
        """
        self.namer="""
        You are part of an AI-powered legal research tool, provide a name for the new chat which a user created on the tool. The name
        should be short (not more than 7 words) and should be based on the user's question. Return a json format response with structure
        {'name':name of chat}.
        """

        self.phrases="""
        You are part of an AI agent used for legal research in Zimbabwe. The user asks questions and the agent is required to
        do a cosine similarity search in a vector database. However, sometimes the user's questions are not enough to generate
        accurate results from the vector search. Using the user's question (request) and the history in the chat as context,
        create search phrases that are necessary for an accurate cosine search in the vector database containing case law or
        legislations. You should return in json format of structure {'phrases':[...list of phrases]}. Your phrases should be able
        to return accurate result hence they should relevant to what the user is researching, should consider the table being searched
        and they should be specific. The number of phrases to return and the name of vector database table to be searched is specified
        at the start of the user's question.
        """

    # a tool for generating a chat name
    def naming(self, prompt):
        messages = [{"role": "system", "content": self.namer}]
        messages.append({"role": "user", "content": prompt})
        answ = self.gpt.json_gpt(messages, 20)
        answer=json.loads(answ)

        return answer['name']

    # a tool for generating text
    def assistant(self, prompt, size,history):
        messages = [{"role": "system", "content": self.system}]
        for message in history:
            messages.append({"role": "user", "content": message['user']})
            messages.append({"role": "assistant", "content": str(message['system'])})
        messages.append({"role": "user", "content": prompt})
        answ = self.gpt.json_gpt(messages, size)
        answer=json.loads(answ)
        answer['citations']=[]
        answer1=json.dumps(answer)
        return answer1, []

    def phraser(self, prompt, history, table, scope):
        messages = [{"role": "system", "content": self.phrases}]
        for message in history:
            messages.append({"role": "user", "content": message['user']})
            messages.append({"role": "assistant", "content": str(message['system'])})
        messages.append({"role": "user", "content": 'Table to be searched: '+ table +', Number of phrases needed: ' +str(scope)+ '. User question: '+ prompt})
        answ = self.gpt.json_gpt(messages, 4060)
        answer=json.loads(answ)
        return answer['phrases']

    def load_unique(self,data):
        unique_docs = set()
        for item in data:
            unique_docs.add((item['citation'],item['table'],item['table_id'],item['file_id'],item['filename']))
        sources=[{'citation': citation, 'table': item['table'], 'table_id': table_id, 'file_id': file_id, 'filename': filename} for citation, table, table_id, file_id, filename in unique_docs]
        return sources

    def load_unique_docu(self,data):
        unique_docs = set()
        for item in data:
            unique_docs.add((item['citation'],item['table'],item['table_id'],item['file_id'],item['filename'],item['document']))
        sources=[{'citation': citation, 'table': item['table'], 'table_id': table_id, 'file_id': file_id, 'filename': filename, 'document':document} for citation, table, table_id, file_id, filename, document in unique_docs]
        return sources

    # tool for retrieving from table and answer
    def research(self, table, prompt, sources):
        temp=[{'citation':item['citation'],'content':item['document']} for item in sources]
        context = "Data: " + str(temp) + "\n Research question:" + prompt
        messages = [{"role": "system", "content": self.researcher}]
        messages.append({"role": "user", "content": context})
        answ = self.gpt.json_gpt(messages, size)
        answer=json.loads(answ)
        answer['citations']=[{'citation': item['citation'], 'table': table, 'table_id': item['table_id'], 'file_id': item['file_id'], 'filename': item['filename']} for item in sources]
        answer1=json.dumps(answer)
        return answer1, sources

    def single_step(self, table, prompt, history, document, k=3, scope=1):
        #first generate phrases
        phrases=self.phraser(prompt, history, table, scope)
        raw_sources=[]
        for phrase in phrases:
            #search from phrases
            raw_sources.extend(self.euclid.search(table, phrase, k))

        #RAG for answer
        sources=self.load_unique_docu(raw_sources)
        temp=[{'citation':item['citation'],'content':item['document']} for item in sources]
        context = "Data: " + str(temp) + "\n Prompt:" + prompt
        if document!='':
            context="User's Document: "+document+"\n "+ context
        messages = [{"role": "system", "content": self.system}]
        for message in history:
            messages.append({"role": "user", "content": message['user']})
            messages.append({"role": "assistant", "content": str(message['system'])})
        messages.append({"role": "user", "content": context})
        answ = self.gpt.json_gpt(messages, 4090)
        answer=json.loads(answ)
        answer['phrases']=phrases
        sources=self.load_unique(sources)
        answer1=json.dumps(answer)
        return answer1, sources

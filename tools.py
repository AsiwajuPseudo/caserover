import os
import json
from gpt import GPT

class Tools:
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
        5. map- for presenting geolocation data. Format={'type':'map','data':{'region':region,'resolution':resolution,'mapData':[...values]},}
          the region is text string a ISO-3166-1 alpha-2 code identifying a country or, continent or a sub-continent, specified by its 3-digit code, e.g., '011' for Western Africa
          resolution is for the map borders and it can only be between 'countries' or 'provinces'
          mapData conatins values which is an array which contains a list of array of each containing 2 values i.e [value1, value2].
           The first value in the array is the pair [resolution name, value] where the resolution value is either 'Country' or 'Province' and value describes the statistics e.g population, cases etc.
           The other values are the actual map data e.g. ['Zambia':15000]
        6. pie chart- for presenting graphical data suitable for a pie chart. Format={'type':'pie chart','data':{'title':title of chart,'values':[...values]},}
          values is an array which has a list of arrays with two values, the first array being [data name, value name] e.g. ['Country','population'] and the other arrays have the data e.g ['Mali',20]
        7. bar chart-for presenting data on a vertical bar chart. Format={'type':'bar chart','data':{'vAxis':vertical axis name,'hAxis':horizontal axis name,'values':[...values]},}
          values is an array which has a list of arrays with 2 or more values, first array in the list contanins identification data e.g ['City', '2010 Population', '2000 Population']
          The other arrays will then contain the actual values e.g. ['Chicago, IL', 2695000, 2896000]
          Please note the arrays can be of more than 2 or 3 values.
        8. area chart-for presenting data on area chart(suitable for line chart too). Format={'type':'area chart','data':{'hAxis':horizontal axis name,'values':[...values]},}
          values is an array which has a list of arrays with 2 or more values, first array in the list contanins identification data e.g ["Year", "Sales", "Expenses"]
          The other arrays will then contain the actual values e.g. ["2013", 1000, 400]
          Please note the arrays can be of more than 2 or 3 values.


        Your answer should be proper json data.
        Do not put 'None' or 'Null' or blank where a numerical value is required, if there is no sufficient numeriacal data provided then put your own estimates appropriately.
        You should assist the user using any data provided by the user or your knowledge.
        If the user provides that is not relevant to what they want assistance on, use your knowledge and if you have knowledge about the issue then tell the user that.
        If you use any of the data provided by the user in any section, then add the path or url of the source to the section's sources. The sources can be empty or contain more than 1 source.
        Format of sources array value is {'name':name of source,'access':url or name of document used as source}.
        Do not put an new lines (\n) or tabs (\t) or anything of that nature in your response and your answer should not be of more than 4000 tokens.
        """
        self.namer="""
        You are part of an AI-powered legal research tool, provide a name for the new chat which a user created on the tool. The name
        should be short (not more than 7 words) and should be based on the user's question. Return a json format response with structure
        {'name':name of chat}.
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

    # tool for retrieving from table and answer
    def rag(self, table, prompt, document, history, k=3, size=500):
        data = self.euclid.search(table, prompt, k)
        temp=[{'citation':item['citation'],'content':item['document']} for item in data]
        context = "Data: " + str(temp) + "\n Prompt:" + prompt
        if document!='':
            context="My Document(s): "+document+'  \n'+ context
        messages = [{"role": "system", "content": self.system}]
        for message in history:
            messages.append({"role": "user", "content": message['user']})
            messages.append({"role": "assistant", "content": str(message['system'])})
        messages.append({"role": "user", "content": context})
        unique_styles = set()
        for item in data:
            unique_styles.add((item['citation'],table,item['table_id'],item['file_id'],item['filename']))
        sources=[{'citation': citation, 'table': table, 'table_id': table_id, 'file_id': file_id, 'filename': filename} for citation, table, table_id, file_id, filename in unique_styles]
        answ = self.gpt.json_gpt(messages, size)
        answer=json.loads(answ)
        answer['citations']=sources
        answer1=json.dumps(answer)
        return answer1, sources

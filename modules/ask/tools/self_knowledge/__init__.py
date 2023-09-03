import os

from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.document_loaders import TextLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma

from config import Config
from ..utils import AkariTool

docs = [os.path.join(os.path.dirname(__file__), 'src', file)
        for file in os.listdir(os.path.join(os.path.dirname(__file__), 'src'))]
texts = []

for doc in docs:
    loader = TextLoader(doc, 'utf-8')
    documents = loader.load()
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    for i in text_splitter.split_documents(documents):
        texts.append(i)

embeddings = OpenAIEmbeddings(openai_api_key=Config('openai_api_key'))
doc_search = Chroma.from_documents(
    texts,
    embeddings,
    collection_name='myself',
    persist_directory=os.path.join(
        os.path.dirname(__file__),
        'data'))
doc_search.persist()
llm = ChatOpenAI(
    temperature=0,
    openai_api_key=Config('openai_api_key'),
    model_kwargs={
        'frequency_penalty': 0.0,
        'presence_penalty': 0.0})
self_knowledge = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=doc_search.as_retriever(
        search_kwargs={
            "k": 1}))


async def self_knowledge_func(query: str):
    return await self_knowledge.arun(query)


self_knowledge_tool = AkariTool.from_function(
    func=self_knowledge_func,
    description='Get facts about yourself, Akaribot. Useful for when you need to answer questions about yourself if the user is curious. Input should be a full question in English.'
)

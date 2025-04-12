import os
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub
from langchain.chains import RetrievalQA

def load_or_create_qa_chain():
    folder_path = os.getcwd()
    all_docs = []

    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    for item in data:
                        name = item.get("name", "Unknown")
                        ticker = item.get("ticker", "Unknown")
                        for text in item.get("clean_data", []):
                            if text:
                                doc = Document(
                                    page_content=text,
                                    metadata={
                                        "name": name,
                                        "ticker": ticker,
                                        "source_file": filename
                                    }
                                )
                                all_docs.append(doc)
                except json.JSONDecodeError:
                    print(f"Skipping bad JSON: {filename}")

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunked_docs = text_splitter.split_documents(all_docs)

    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    db_path = './chroma_db'
    if os.path.exists(db_path):
        db = Chroma(persist_directory=db_path, embedding_function=embedding_model)
    else:
        db = Chroma.from_documents(chunked_docs, embedding=embedding_model, persist_directory=db_path)
        db.persist()

    llm = HuggingFaceHub(
        repo_id="mistralai/Mistral-7B-Instruct-v0.1",
        model_kwargs={"temperature": 0.7, "max_new_tokens": 512}
    )

    retriever = db.as_retriever(search_kwargs={"k": 4})
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )

    return qa_chain

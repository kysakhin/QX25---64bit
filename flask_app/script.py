import os
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain_community.llms import HuggingFaceHub

# Path to the folder containing your JSON files
folder_path = os.getcwd()
all_docs = []

# Loading json and parsing metadata for context
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
                        if text:  # Only add non-empty text
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
                print(f"Error decoding JSON from {filename}. Skipping file.")

print(f"Loaded {len(all_docs)} documents.")

# Text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)
chunked_docs = text_splitter.split_documents(all_docs)
print(f"Total chunks: {len(chunked_docs)}")

# ChromaDB + Embedding
try:
    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Check if DB already exists
    db_path = './chroma_db'
    if os.path.exists(db_path):
        print(f"Loading existing database from {db_path}")
        db = Chroma(
            persist_directory=db_path,
            embedding_function=embedding_model
        )
    else:
        print("Creating new vector database")
        db = Chroma.from_documents(
            documents=chunked_docs,
            embedding=embedding_model,
            persist_directory=db_path
        )
        db.persist()
        print(f"Database saved to {db_path}")
    
    # # Set up OpenAI chat model (make sure OPENAI_API_KEY is set in your environment)
    # llm = ChatOpenAI(
    #     model="gpt-3.5-turbo",
    #     temperature=0.2  # Keep it low for factual answers
    # )
    
    llm = HuggingFaceHub(
        repo_id="mistralai/Mistral-7B-Instruct-v0.1",
        model_kwargs={"temperature": 0.7, "max_new_tokens": 512}
    )

    # QA Chain
    retriever = db.as_retriever(search_kwargs={"k": 4})
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )
    
    # Example query
    query = "What is the risk level of ICICI Prudential fund?"
    print(f"\nExecuting query: '{query}'")
    response = qa_chain.invoke(query)
    
    print("\nAnswer:")
    print(response['result'])
    print("\nSources:")
    for i, doc in enumerate(response['source_documents']):
        print(f"Source {i+1}:")
        print(f"  Metadata: {doc.metadata}")
        print(f"  Content: {doc.page_content[:100]}...")
        print()

except Exception as e:
    print(f"Error: {str(e)}")
    print("If this is a dependency issue, try running:")
    print("pip install --upgrade langchain langchain-community langchain-openai chromadb sentence-transformers")

from flask import Flask, request, jsonify
from backend import load_or_create_qa_chain

app = Flask(__name__)
qa_chain = load_or_create_qa_chain()

@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.json
    question = data.get("question", "")

    if not question:
        return jsonify({"error": "Please provide a question."}), 400

    response = qa_chain.invoke(question)
    
    return jsonify({
        "answer": response["result"],
        "sources": [
            {
                "metadata": doc.metadata,
                "content_snippet": doc.page_content[:100]
            } for doc in response["source_documents"]
        ]
    })

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request, jsonify, send_from_directory, render_template_string
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from formatting import criar_docx  
from template import template_1
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Diretórios definidos por variáveis de ambiente
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER")

def carregar_documentos(file_path):
    documentos = []
    loader = PyMuPDFLoader(file_path=file_path)
    documentos.extend(loader.load())
    return documentos

embedding = OpenAIEmbeddings()
prompt = PromptTemplate(
    input_variables=["message", "dados"],
    template=template_1
)

llm = ChatOpenAI(temperature=0.1, model="gpt-4")
chain = LLMChain(llm=llm, prompt=prompt)

def gerar_resposta(message, dados):
    response = chain.run({"message": message, "dados": "\n".join(dados)})
    return response

@app.route('/')
def index():
    index_html_path = os.getenv("FRONT_OP")
    if not index_html_path:
        return jsonify({"error": "O caminho do arquivo HTML não está definido."}), 500
    try:
        with open(index_html_path, 'r') as file:
            index_html = file.read()
        return render_template_string(index_html)
    except FileNotFoundError:
        return jsonify({"error": "Arquivo HTML não encontrado."}), 404

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "Por favor, forneça um arquivo PDF."}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado."}), 400
    
    if file and file.filename.endswith('.pdf'):
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        file.save(file_path)
        
        documents = carregar_documentos(file_path)
        db = FAISS.from_documents(documents, embedding)
        
        def consulta_base(query):
            similares = db.similarity_search(query)
            return [doc.page_content for doc in similares]

        dados = consulta_base("Exemplo de consulta")
        resposta = gerar_resposta("Exemplo de mensagem do usuário", dados)
        
        # Salvar o arquivo no OUTPUT_FOLDER
        output_file_path = os.path.join(OUTPUT_FOLDER, f"ANALIZADO-{file.filename}")
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
        
        nome_arquivo = criar_docx(resposta, output_file_path)
        
        # Verifique se o arquivo foi criado com sucesso
        if not os.path.exists(nome_arquivo):
            return jsonify({"error": "Falha ao criar o arquivo .docx."}), 500

        # Retorna a URL do arquivo para download
        return jsonify({"file_url": f"/download/{os.path.basename(nome_arquivo)}"})

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    # Serve o arquivo do diretório de saída
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(OUTPUT_FOLDER, filename)
    else:
        return jsonify({"error": "Arquivo não encontrado."}), 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

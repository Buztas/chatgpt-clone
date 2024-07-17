import os
import getpass
import uuid
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage
)
from langchain_core.chat_history import (
    BaseChatMessageHistory,
    InMemoryChatMessageHistory
)
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import streamlit as st
from streamlit_chat import message
from dotenv import load_dotenv
import requests
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
import tempfile
import hashlib

store = {}

messages = []

uploaded_files = []

retriever = None

persist_directory = "chroma_db"

BASE_URL = "http://localhost:5000"


#ERRORS
#1. 


def init():
    global uploaded_files, retriever 

    load_dotenv()

    if os.getenv("OPENAI_API_KEY") is None or os.getenv("OPENAI_API_KEY") == "":
        print("OPENAI_API_KEY IS NOT SET")
        exit(1)
    else:
        print("OPENAI_API_KEY IS SET")

    st.set_page_config(
        page_title="CustomGPT",
        page_icon="🤖"
    )

    st.header("Your own ChatGPT")

       
    saved_files = get_saved_files()
    if saved_files:
        st.sidebar.write("Previously processed files:")
        for file in saved_files:
            if isinstance(file, dict) and 'file_name' in file:
                st.sidebar.write(file['file_name'])
        
    if st.sidebar.button("Use saved files"):
        with st.spinner("Processing saved files..."):
            retriever = process_pdfs(saved_files)
            if retriever:
                st.session_state['retriever'] = retriever
                st.success("Saved files processed successfully!")
            else:
                st.error("Failed to process saved files.")
        st.rerun()
    
    with st.sidebar:
        uploaded_files = st.file_uploader("Upload PDF files", accept_multiple_files=True)

        if st.button("Process") and uploaded_files:
            with st.spinner():
                st.session_state['retriever'] = process_pdfs(uploaded_files)

    display_sessions()



def process_pdfs(files):
    documents = []
    for file in files:
        if isinstance(file, dict):  # Saved file info
            file_path = file.get('file_path')
            if file_path and os.path.exists(file_path):
                try:
                    loader = PyPDFLoader(file_path)
                    documents.extend(loader.load())
                    print(f"Successfully loaded {file.get('file_name')}")
                except Exception as e:
                    st.warning(f"Error loading {file.get('file_name')}: {str(e)}")
            else:
                st.warning(f"File not found: {file.get('file_name')} at {file_path}")
        else:  # Uploaded file
            file_path = os.path.join("uploads", file.name)
            os.makedirs("./uploads", exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(file.getvalue())
            try:
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
                print(f"Successfully loaded {file.name}")
            except Exception as e:
                st.warning(f"Error loading {file.name}: {str(e)}")
            # finally:
            #     os.unlink(temp_file_path)

            if save_file_info(file.name, file_path):
                st.success(f"Saved info for file: {file.name}")
            else:
                st.warning(f"Failed to save info for file: {file.name}")

    if not documents:
        st.error("No documents were successfully loaded. Please check your files and try again.")
        return None

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)

    if not splits:
        st.error("No text content was extracted from the documents. Please check your files and try again.")
        return None

    try:
        embedding_function = OpenAIEmbeddings()
        if os.path.exists(persist_directory):
            vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embedding_function)
            if splits:  # If there are new documents
                vectorstore.add_documents(splits)
        else:
            vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embedding_function,
                persist_directory=persist_directory
            )
        st.session_state['retriever'] = vectorstore.as_retriever()
        return st.session_state['retriever']
    except Exception as e:
        st.error(f"Error creating vectorstore: {str(e)}")
        return None



def create_new_chat():
    try:
        print(f"{BASE_URL}/new-chat")
        response = requests.post(f"{BASE_URL}/new-chat")
        if response.status_code == 200:
            new_session_id = response.json().get('session_id')
            st.session_state['session_id'] = new_session_id
            st.rerun() #this reloads the page when we make the new chat
        else:
            st.error(f"Failed to create new chat. Status code: {response.status_code}")
            print(f"Failed to create new chat. Status code: {response.status_code}")
    except requests.RequestException as e:
        st.error(f"An error occured: {str(e)}")





def display_sessions():
    with st.sidebar:
        if st.button("New chat", key="create_new" ):
            create_new_chat()

    try:
        response = requests.get(f"{BASE_URL}/get-all-sessions")
        if response.status_code == 200:
            sessions = response.json()
        else:
            st.sidebar.error("Failed to fetch sessions")
            sessions = []
    except requests.RequestException as e:
        st.sidebar.error(f"An error occured: {str(e)}")
        sessions = []

    st.sidebar.title("Your chats")

    for session_id in sessions:
        if st.sidebar.button(f"Chat {session_id[:8]}", key=session_id):
            st.session_state['session_id'] = session_id
            st.rerun()




def get_history(session_id):
    try:
        response = requests.get(f"{BASE_URL}/get-history/{session_id}")
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch chat history. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        st.error(f"An error occurred while fetching chat history: {str(e)}")
        return []




def add_message(session_id, message):
    try:
        response = requests.post(f"{BASE_URL}/add-message/{session_id}", json={"message": message})
        if response.status_code != 200:
            st.error(f"Failed to add message. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        st.error(f"An error occured while adding message: {str(e)}")
        return []





def get_ai_response(new_message, chat_history):

    model = ChatOpenAI(model="gpt-4o")  

    messages = [
        SystemMessage(content="You are a helpful assistant. Answer all questions to the best of your ability.")
    ]
    for msg in chat_history:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            messages.append(AIMessage(content=msg['content']))
    
    # Add the new message
    messages.append(HumanMessage(content=new_message))

    # Generate the AI response
    ai_message = model.invoke(messages)

    # Return the content of the AI's response
    return ai_message.content





def display_chat(session_id):

    if session_id is None:
        st.write("No active chat session. Choose an existing one or create a new one.")
    else:
        st.subheader(f"Chat session: {session_id[:8]}...")

    chat_history = get_history(session_id)

    for msg in chat_history:
        if msg['role'] == 'user':
            st.chat_message("user").write(msg['content'])
        elif msg['role'] == 'assistant':
            st.chat_message("assistant").write(msg['content'])
        elif msg['role'] == 'system':
            st.text(f"System: {msg['content']}")




def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


def save_file_info(file_name, file_path):
    try:
        response = requests.post(f"{BASE_URL}/save-file-info", json ={
            "file_name" : file_name,
            "file_path" : file_path,
        })
        print(response.status_code)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Failed to save file info. Status code: {response.status_code}")
            return False
    except requests.RequestException as e:
        st.error(f"An error occured while saving file info: {str(e)}")
        return False

def get_saved_files():
    try:
        response = requests.get(f"{BASE_URL}/get-files-info")
        print(response.status_code)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch saved files. Status code: {response.status_code}")
            return []
    except requests.RequestException as e:
        st.error(f"An error occured while fetching saved files: {str(e)}")
        return []


def main():
    init()

    chat_status = st.radio(
        "Chat type:",
        [
            "Query mode",
            "Search mode",
            "LLM Chat"
        ]
    )

    if "retriever" not in st.session_state or st.session_state['retriever'] is None:
        # Try to load existing vectorstore
        persist_directory = "chroma_db"
        if os.path.exists(persist_directory):
            try:
                vectorstore = Chroma(persist_directory=persist_directory, embedding_function=OpenAIEmbeddings())
                st.session_state['retriever'] = vectorstore.as_retriever()
            except Exception as e:
                st.error(f"Error loading existing vectorstore: {str(e)}")

    retriever = st.session_state['retriever']            

    if "messages" not in st.session_state:
        st.session_state['messages'] = [
            SystemMessage(content="You are a helpful assistant. Answer all questions to the best of your ability.")
        ]

    if 'session_id' not in st.session_state or st.session_state['session_id'] is None:
        st.write("Create a new chat or select an existing one")
        return

    if "topics" not in st.session_state:
        st.session_state['topics'] = {}   

    session_id = st.session_state['session_id']

    # Display the current chat
    display_chat(session_id)

    # Set dropdown for models later
    config = {"configurable": {"session_id": session_id}}

    # Replace with chain later
    llm = ChatOpenAI(model="gpt-4")  # Changed from "gpt-4o" to "gpt-4"

    input_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Answer all questions to the best of your ability.",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = input_template | llm

    with_message_history = RunnableWithMessageHistory(chain, get_session_history, input_messages_key="messages")

    prompt = st.chat_input("Ask the GPT something!")

    qa_prompt = ChatPromptTemplate.from_template("""You are a helpful AI assistant. Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

        Context: {context}

        Question: {input}

    Answer:""")

    print("retriever" , retriever)

    if chat_status == "Query mode":
        if retriever is None:
            st.warning("Please upload and process PDF files first.")
        else:
            question_answers_chain = create_stuff_documents_chain(llm,qa_prompt)
            rag_chain = create_retrieval_chain(retriever, question_answers_chain)

    if prompt:
        st.chat_message("user").write(prompt)
        add_message(session_id, {"role": "user", "content": prompt})

        response_placeholder = st.empty()
        response_text = ""
        source_text = []
        #Fix below messy, code being reused

        if chat_status == "Query mode" and retriever is not None:
            with st.spinner("Generating response..."):
                for chunk in rag_chain.stream({"input": prompt}):
                    if 'context' in chunk:
                        source_text = '\nPage: ' + str(chunk['context'][0].metadata['page']) + '\n\nSource:' + chunk['context'][0].metadata['source'] + '\n\nPage_Content:' +  chunk['context'][1].page_content
                    if 'answer' in chunk:
                        response_text += chunk['answer']
                        response_placeholder.chat_message("ai").write(response_text)
        else:
            for r in with_message_history.stream(
                {
                    "messages": get_history(session_id)
                },
                config=config,
            ):
                response_text += r.content
                response_placeholder.chat_message("ai").write(response_text)

        response_text += '\n' + source_text

        print(response_text)
        add_message(session_id, {"role": "assistant", "content": response_text})

        # Rerun to update the chat display
        st.rerun()

if __name__ == "__main__":
    main()



# def start_new_chat():
#     new_session_id = str(uuid.uuid4())
#     st.session_state['sessions'].append(new_session_id)
#     st.session_state['current_session'] = new_session_id
#     st.session_state[new_session_id] = [SystemMessage(content="You are a helpful assistant. Answer all questions to the best of your ability.")]
#     st.session_state['topics'][new_session_id] = "New Chat"


# def switch_chat(session_id: str):
#     st.session_state['current_session'] = session_id    
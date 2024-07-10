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

store = {}

messages = []

BASE_URL = "http://localhost:5000"

def init():
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

    display_sessions()

def create_new_chat():
    try:
        print(f"{BASE_URL}/new-chat")
        response = requests.post(f"{BASE_URL}/new-chat")
        if response.status_code == 200:
            new_session_id = response.json().get('session_id')
            st.session_state['session_id'] = new_session_id
            st.experimental_rerun() #this reloads the page when we make the new chat
        else:
            st.error(f"Failed to create new chat. Status code: {response.status_code}")
            print(f"Failed to create new chat. Status code: {response.status_code}")
    except requests.RequestException as e:
        st.error(f"An error occured: {str(e)}")

def display_sessions():
    with st.sidebar:
        if st.button("Create new chat"):
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
            st.experimental_rerun()

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

def main():
    init()

    if "messages" not in st.session_state:
        st.session_state['messages'] = [
            SystemMessage(content="You are a helpful assistant. Answer all questions to the best of your ability.")
        ]

    if "session_id" not in st.session_state:
        create_new_chat()

    if "topics" not in st.session_state:
        st.session_state['topics'] = {}

    session_id = st.session_state['session_id']

    # Display the current chat
    display_chat(session_id)

    # Set dropdown for models later
    config = {"configurable": {"session_id": session_id}}

    # Replace with chain later
    model = ChatOpenAI(model="gpt-4")  # Changed from "gpt-4o" to "gpt-4"

    input_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Answer all questions to the best of your ability.",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = input_template | model

    with_message_history = RunnableWithMessageHistory(chain, get_session_history, input_messages_key="messages")

    prompt = st.chat_input("Ask the GPT something!")

    if prompt:
        st.chat_message("user").write(prompt)
        add_message(session_id, {"role": "user", "content": prompt})

        response_placeholder = st.empty()
        response_text = ""

        for r in with_message_history.stream(
            {
                "messages": get_history(session_id)
            },
            config=config,
        ):
            response_text += r.content
            response_placeholder.chat_message("ai").write(response_text)

        add_message(session_id, {"role": "assistant", "content": response_text})

        # Rerun to update the chat display
        st.experimental_rerun()

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
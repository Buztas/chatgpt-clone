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

store = {}

messages = []

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

    with st.sidebar:
        st.button("Your first chat")

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
        st.session_state['session_id'] = os.urandom(8).hex()

    if "topics" not in st.session_state:
        st.session_state['topics'] = {}



    session_id = st.session_state['session_id']

    # Set dropdown for models later
    config = {"configurable": {"session_id": session_id}}

    # Replace with chain later
    model = ChatOpenAI(model="gpt-4o")

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

    # Display the chat history
    for msg in st.session_state['messages']:
        if isinstance(msg, HumanMessage):
            st.chat_message("user").write(msg.content)
        elif isinstance(msg, AIMessage):
            st.chat_message("ai").write(msg.content)    
        elif isinstance(msg, SystemMessage):
                st.write(msg.content)    

    if prompt:

        st.chat_message("user").write(prompt)

        st.session_state['messages'].append(HumanMessage(content=prompt))

        response_placeholder = st.empty()
        response_text = ""

        for r in with_message_history.stream(
            {
                "messages": st.session_state['messages']
            },
            config=config,
        ):
            response_text += r.content
            response_placeholder.chat_message("ai").write(response_text)


        st.session_state['messages'].append(AIMessage(content=response_text))

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
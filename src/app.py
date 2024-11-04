import streamlit as st
from chatbot import Chatbot

def main():
    # Create an instance of the chatbot
    chatbot = Chatbot()

    # Set the title and description of the app
    st.title("Streamlit Chat App")
    st.markdown("Welcome to the chat app powered by Chatbot!")

    # Get user input
    user_input = st.text_input("User Input")

    # Generate response using the chatbot
    response = chatbot.generate_response(user_input)

    # Display the response
    st.text_area("Chatbot Response", value=response, height=200)

if __name__ == "__main__":
    main()
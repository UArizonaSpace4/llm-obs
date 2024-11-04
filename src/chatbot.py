import streamlit as st
import openai

# Set up OpenAI API credentials
openai.api_key = "YOUR_OPENAI_API_KEY"

# Define function to generate chatbot response
def generate_response(input_text):
    response = openai.Completion.create(
        engine="davinci",
        prompt=input_text,
        max_tokens=50,
        temperature=0.7,
        n=1,
        stop=None,
        temperature=0.7
    )
    return response.choices[0].text.strip()

# Streamlit app code
def main():
    st.title("Chatbot App")
    user_input = st.text_input("User Input", "")
    
    if st.button("Send"):
        response = generate_response(user_input)
        st.text_area("Chatbot Response", response, height=200)

if __name__ == "__main__":
    main()
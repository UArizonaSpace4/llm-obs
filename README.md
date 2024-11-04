# Streamlit Chat App

This is a simple chat application built using Streamlit and OpenAI API. The app allows users to have interactive conversations with a chatbot powered by OpenAI's language model.

## Project Structure

The project has the following file structure:

```
streamlit-chat-app
├── src
│   ├── app.py
│   └── chatbot.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

- `src/app.py`: This file is the main script of the Streamlit app. It uses high-level components from Streamlit to create a user interface for the chatbot. It imports the `chatbot.py` module to handle the chatbot logic.

- `src/chatbot.py`: This file contains the logic for the chatbot. It makes calls to the OpenAI API to generate responses based on user input.

- `requirements.txt`: This file lists the Python dependencies required for the project. It includes packages such as Streamlit and OpenAI.

- `Dockerfile`: This file is used to build the Docker image for the application. It specifies the base image, installs the necessary dependencies, and sets the entry point to run the `app.py` script.

- `docker-compose.yml`: This file is used to define the Docker Compose configuration for the project. It specifies the services, networks, and volumes required to run the application.

## Getting Started

To set up and run the Streamlit chat app, follow these steps:

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/streamlit-chat-app.git
   ```

2. Navigate to the project directory:

   ```bash
   cd streamlit-chat-app
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the application using Streamlit:

   ```bash
   streamlit run src/app.py
   ```

5. Access the chat app in your browser at `http://localhost:8501`.

## Docker Support

Alternatively, you can also run the Streamlit chat app using Docker. Make sure you have Docker installed on your system.

1. Build the Docker image:

   ```bash
   docker build -t streamlit-chat-app .
   ```

2. Run the Docker container:

   ```bash
   docker run -p 8501:8501 streamlit-chat-app
   ```

3. Access the chat app in your browser at `http://localhost:8501`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Feel free to explore and modify the code to suit your needs. Happy chatting!
# Space4 Chatbot

## Preliminaries

- Clone the [observation planner repository](https://github.com/UArizonaSpace4/obs-planner/tree/victor) and rename the folder from `obs-planner` to `obs_planner`
- Copy SatellitePredictor.exe in `obs_planner/dockerfiles`
- Copy SatellitePredictor/ (the folder containing program data) in `obs_planner/dockerfiles`

## Environment configuration

Create a `.env` file in the root directory with the following variables:

- `OPENAI_API_KEY`: Your OpenAI API key for the chatbot
- `OBS_PLANNER_PORT`: Port for the observation planner service (default: 1929)
- `OBS_PLANNER_ROOT`: Absolute path to the observation planner directory
- `SAT_PREDICTOR_OUTPUT_DIR`: Directory where satellite prediction outputs will be stored
- `DB_USER`: PostgreSQL database username
- `DB_PASSWORD`: PostgreSQL database password  
- `DB_NAME`: Database name (default: targets)
- `IS_MOCK`: Set to False for real satellite predictions, True for testing
- `UID`: User ID for Docker container permissions (get with `id -u`)
- `GID`: Group ID for Docker container permissions (get with `id -g`)

## Run

```sh
docker compose build
docker compose up
```

The app will be deployed in port 8501. Wait a aminute before trying it out for the first time,
the satellite predictor takes a while to be fully running and listening to requests.
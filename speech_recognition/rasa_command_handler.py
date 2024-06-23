import os
import random
import string
import requests
from logging import Logger

RASA_URL = "http://localhost:5005"


def handle_command(command: str, logger: Logger) -> str:
    rasa_url = os.getenv("RASA_URL", RASA_URL)
    conversation_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(16))
    request = {
        "text": command,
        "sender": "user"
    }
    response = requests.post(rasa_url + "/conversations/{}/messages".format(conversation_id), json=request)
    if response.status_code != 200:
        raise IOError("Error talking to RASA server: {}".format(response.content))
    message = response.json()
    logger.info("Recognized intent: %s | entities: %s", message["latest_message"]["intent"],
                message["latest_message"]["entities"])
    response = requests.post(rasa_url + "/conversations/{}/predict".format(conversation_id))
    if response.status_code != 200:
        raise IOError("Error talking to RASA server: {}".format(response.content))
    message = response.json()
    logger.info("Identified action: %s | policy: %s | confidence: %s", message["scores"][0], message["policy"],
                message["confidence"])
    # trigger action
    request = {
        "name": message["scores"][0]['action'],
        "policy": message["policy"],
        "confidence": message["confidence"]
    }
    response = requests.post(rasa_url + "/conversations/{}/execute".format(conversation_id), json=request)
    if response.status_code != 200:
        raise IOError("Error talking to RASA server: {}".format(response.content))
    message = response.json()
    if message:
        return message["message"]["messages"][0]["text"]
    return ""


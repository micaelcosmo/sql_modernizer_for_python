import os
import pytest
from dotenv import load_dotenv

# Força o carregamento do .env antes de qualquer teste rodar
@pytest.fixture(scope="session", autouse=True)
def load_env():
    load_dotenv()
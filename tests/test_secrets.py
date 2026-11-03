import keyring
import keyring.errors
import pytest
from keyring.backend import KeyringBackend

from grepleo import secrets


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self.data = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        try:
            del self.data[(service, username)]
        except KeyError as error:
            raise keyring.errors.PasswordDeleteError("no hay") from error


class BrokenKeyring(MemoryKeyring):
    def get_password(self, service, username):
        raise keyring.errors.KeyringError("sin llavero")


@pytest.fixture
def memory():
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def test_the_token_goes_to_the_keyring_and_can_be_cleared(memory):
    assert secrets.get_token() is None
    secrets.set_token("  apify_api_x  ")
    assert secrets.get_token() == "apify_api_x" and memory.data == {("grepleo", "apify_token"): "apify_api_x"}
    secrets.set_token("")
    assert secrets.get_token() is None
    secrets.clear_token()          # borrar lo que no hay no es un error


def test_a_missing_keyring_is_reported_clearly():
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        with pytest.raises(secrets.SecretsError, match="sin llavero"):
            secrets.get_token()
    finally:
        keyring.set_keyring(previous)

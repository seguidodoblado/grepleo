import io
import json
import urllib.error
from pathlib import Path

from grepleo.geocode import USER_AGENT, GeocodeError, Geocoder, clean_place, geocode_places
from grepleo.storage import Store


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def opener_for(answers):
    """Un opener falso: devuelve cada respuesta de la lista (o lanza la excepción) y guarda las peticiones."""
    sent = []

    def opener(request, timeout):
        sent.append(request)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Response(json.dumps(answer).encode())

    opener.sent = sent
    return opener


def test_only_real_places_are_asked_for_and_noise_is_removed():
    assert clean_place("Madrid") == "Madrid" and clean_place(" Arlington, VA ") == "Arlington, VA"
    assert clean_place("Zaragoza Ciudad") == "Zaragoza" and clean_place("Sevilla provincia") == "Sevilla"
    assert clean_place("Alicante/Alacant") == "Alicante" and clean_place("Barcelona Ciudad") == "Barcelona"
    for not_a_place in ("100% remoto", "En remoto", "International", "Teletrabajo", "Home office", "", "  "):
        assert clean_place(not_a_place) == ""


def test_the_geocoder_asks_nominatim_with_the_app_agent_and_reads_the_first_result():
    opener = opener_for([[{"lat": "40.4168", "lon": "-3.7038"}], [], {"error": "x"}, [{"lat": "x"}]])
    geocoder = Geocoder(opener)
    assert geocoder.lookup("Madrid") == (40.4168, -3.7038)
    request = opener.sent[0]
    assert request.full_url.startswith("https://nominatim.openstreetmap.org/search?") and "q=Madrid" in request.full_url
    assert request.get_header("User-agent") == USER_AGENT and "Grepleo/" in USER_AGENT
    assert geocoder.lookup("Ninguna parte") is None            # no existe
    assert geocoder.lookup("raro") is None and geocoder.lookup("raro2") is None    # respuestas sin sentido: no existe


def test_network_failures_are_errors_not_unknown_places():
    for failure in (urllib.error.URLError("sin red"), urllib.error.HTTPError("u", 429, "demasiadas", {}, None),
                    TimeoutError("lento")):
        try:
            Geocoder(opener_for([failure])).lookup("Madrid")
        except GeocodeError:
            continue
        raise AssertionError("debía fallar")


def test_places_are_asked_one_by_one_with_a_pause_and_stop_on_error_or_cancel():
    found = []
    pauses = []
    opener = opener_for([[{"lat": "1", "lon": "2"}], [], [{"lat": "3", "lon": "4"}]])
    message = geocode_places(["A", "B", "C"], Geocoder(opener), lambda place, coordinates: found.append((place, coordinates)),
                             pause=1.1, sleep=pauses.append)
    assert message == "" and found == [("A", (1.0, 2.0)), ("B", None), ("C", (3.0, 4.0))]
    assert pauses == [1.1, 1.1]                                # una pausa entre peticiones, no antes de la primera
    found.clear()
    failing = opener_for([[{"lat": "1", "lon": "2"}], urllib.error.URLError("sin red"), [{"lat": "9", "lon": "9"}]])
    message = geocode_places(["A", "B", "C"], Geocoder(failing), lambda place, coordinates: found.append(place),
                             pause=0, sleep=lambda _s: None)
    assert "sin red" in message and found == ["A"]             # al primer fallo se para
    stop = []
    geocode_places(["A", "B"], Geocoder(opener_for([[{"lat": "1", "lon": "2"}]] * 2)),
                   lambda place, coordinates: stop.append(place), cancelled=lambda: bool(stop), pause=0,
                   sleep=lambda _s: None)
    assert stop == ["A"]                                       # cancelada tras el primero


def test_places_are_cached_in_the_database_including_the_ones_that_do_not_exist():
    store = Store(Path(":memory:"))
    assert store.cached_places(["Madrid"]) == {}
    store.save_place("Madrid", (40.4, -3.7))
    store.save_place("Ninguna parte", None)
    assert store.cached_places(["madrid", "Ninguna parte", "Otra"]) == {"madrid": (40.4, -3.7), "Ninguna parte": None}
    store.save_place("MADRID", (41.0, -3.0))                   # sin distinguir mayúsculas; el último manda
    assert store.cached_places(["Madrid"]) == {"Madrid": (41.0, -3.0)}

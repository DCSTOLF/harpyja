"""RED (task 18): `harpyja doctor` preflight.

AC10 — reports rg/deno presence, the configured endpoint URL, and air-gap
status (the same loopback check as the gateway), making no live endpoint call.
"""

import socket

from harpyja.config.doctor import DoctorReport, run_doctor
from harpyja.config.settings import Settings


def _which_stub(present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def test_doctor_reports_rg_presence():
    report = run_doctor(Settings(), which=_which_stub({"rg"}))
    assert report.rg_present is True


def test_doctor_reports_rg_absent():
    report = run_doctor(Settings(), which=_which_stub(set()))
    assert report.rg_present is False


def test_doctor_reports_deno_presence():
    report = run_doctor(Settings(), which=_which_stub({"deno"}))
    assert report.deno_present is True
    assert run_doctor(Settings(), which=_which_stub(set())).deno_present is False


def test_doctor_reports_endpoint_url():
    settings = Settings(lm_api_base="http://127.0.0.1:11434/v1")
    report = run_doctor(settings, which=_which_stub(set()))
    assert isinstance(report, DoctorReport)
    assert report.endpoint_url == "http://127.0.0.1:11434/v1"


def test_doctor_air_gap_pass_for_loopback_endpoint():
    settings = Settings(lm_api_base="http://127.0.0.1:11434/v1")
    assert run_doctor(settings, which=_which_stub(set())).air_gap_ok is True


def test_doctor_air_gap_fail_for_remote_endpoint():
    settings = Settings(lm_api_base="http://8.8.8.8:11434/v1")
    report = run_doctor(settings, which=_which_stub(set()))
    # doctor reports the failure; it never raises
    assert report.air_gap_ok is False


def test_doctor_makes_no_endpoint_call(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("doctor made a network call")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    settings = Settings(lm_api_base="http://127.0.0.1:11434/v1")
    run_doctor(settings, which=_which_stub({"rg", "deno"}))  # must not call out

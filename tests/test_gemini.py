from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app import GEMINI_MODEL, Voucher, _normalize_private_key, extraer_datos_voucher


@pytest.fixture(scope="module")
def sample_pem() -> str:
    """PEM desechable generado en memoria, nunca una credencial real."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@pytest.mark.parametrize(
    "mangle",
    [
        lambda pem: pem,
        lambda pem: pem.replace("\n", "\\n"),
        lambda pem: pem.replace("\n", ""),
        lambda pem: pem.replace("\n", "\r\n"),
        lambda pem: pem.replace("\n", "\n   "),
    ],
    ids=["intacto", "con \\n literal", "sin saltos de línea", "CRLF", "indentado"],
)
def test_normalize_private_key_recupera_pem_valido(sample_pem, mangle):
    mangled = mangle(sample_pem)
    normalized = _normalize_private_key(mangled)
    serialization.load_pem_private_key(normalized.encode(), password=None)


def test_voucher_schema_accepts_valid_payload():
    voucher = Voucher(
        comercio="Supermercado Lider",
        fecha="12/03/2026",
        mes_texto="March",
        monto_total=15990.0,
        iva=2550.0,
        categoria_sugerida="Comida",
    )
    assert voucher.monto_total == 15990.0
    assert voucher.iva == 2550.0


def test_voucher_schema_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        Voucher(fecha="12/03/2026", monto_total=100.0)


def test_extraer_datos_voucher_returns_parsed_voucher():
    fake_voucher = Voucher(
        comercio="Farmacia Cruz Verde",
        fecha="01/01/2026",
        mes_texto="January",
        monto_total=4990.0,
        iva=0.0,
        categoria_sugerida="Salud",
    )
    fake_response = MagicMock(parsed=fake_voucher)
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    resultado = extraer_datos_voucher(fake_client, img="imagen-falsa")

    fake_client.models.generate_content.assert_called_once()
    _, kwargs = fake_client.models.generate_content.call_args
    assert kwargs["model"] == GEMINI_MODEL
    assert kwargs["config"].response_mime_type == "application/json"
    assert kwargs["config"].response_schema is Voucher
    assert resultado == fake_voucher


def test_extraer_datos_voucher_raises_when_parsing_fails():
    fake_response = MagicMock(parsed=None)
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with pytest.raises(ValueError):
        extraer_datos_voucher(fake_client, img="imagen-falsa")

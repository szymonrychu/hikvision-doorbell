# import logging

# from hikvision_doorbell.utils import (
#     b64dec,
#     b64dec_json,
#     b64enc,
#     b64enc_json,
# )

# logger = logging.getLogger(__name__)


# def test_b64enc():
#     assert b64enc("test_data") == "dGVzdF9kYXRh"


# def test_b64dec():
#     assert b64dec("dGVzdF9kYXRh") == "test_data"


# def test_b64enc_json():
#     assert b64enc_json({"test": "test"}) == "eyJ0ZXN0IjogInRlc3QifQ=="


# def test_b64dec_json():
#     assert b64dec_json("eyJ0ZXN0IjoidGVzdCJ9") == {"test": "test"}

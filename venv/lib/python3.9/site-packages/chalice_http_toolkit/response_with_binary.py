from chalice import Response
import os

class ResponseWithBinary(Response):
    """
    Wrapper class to override isBase64Encoded behaviour in the Reponse class.
    Setting isBase64Encoded is usually done to encode Binary content for API Gateway
    so that it knows to decode it.
    """
    isBase64Encoded = False
    isLocal = os.environ.get('STAGE', 'dev') == 'dev'
    def to_dict(self, binary_types=None) -> dict:
        response = super().to_dict(binary_types=binary_types)
        return response
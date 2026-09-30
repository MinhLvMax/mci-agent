import requests


class APIClient:

    def __init__(self, base_url: str):
        self.base_url = base_url

    def post(self, path: str, **kwargs):
        return requests.post(
            f"{self.base_url}{path}",
            **kwargs,
        )

    def get(self, path: str, **kwargs):
        return requests.get(
            f"{self.base_url}{path}",
            **kwargs,
        )

    def delete(self, path: str, **kwargs):
        return requests.delete(
            f"{self.base_url}{path}",
            **kwargs,
        )

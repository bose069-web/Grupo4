import requests
import json

endpoint = "https://iaservicerichard.cognitiveservices.azure.com/"
key = "TU_CLAVE_1"

url = endpoint + "text/analytics/v3.1/sentiment"

headers = {
    "Ocp-Apim-Subscription-Key": key,
    "Content-Type": "application/json"
}

documentos = {
    "documents": [
        {
            "id": "1",
            "language": "es",
            "text": "Me encanta trabajar con Azure."
        },
        {
            "id": "2",
            "language": "es",
            "text": "El servicio es terrible."
        },
        {
            "id": "3",
            "language": "en",
            "text": "This product is amazing."
        },
        {
            "id": "4",
            "language": "en",
            "text": "I am very disappointed."
        },
        {
            "id": "5",
            "language": "es",
            "text": "La aplicación funciona bien aunque es algo lenta."
        }
    ]
}

response = requests.post(url, headers=headers, json=documentos)

print(json.dumps(response.json(), indent=4, ensure_ascii=False))
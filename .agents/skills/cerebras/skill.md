--- 
name: cerebras-inference
description: Utilice esta función para escribir código que llame a un LLM con LiteLLM y OpenRouter, priorizando Cerebras cuando el modelo lo admita y permitiendo fallback a proveedores compatibles.
---

# Llamada a un LLM a través de OpenRouter con Cerebras preferido

Estas instrucciones le permiten escribir código para llamar a un LLM mediante
OpenRouter. Cerebras es el proveedor preferido, no una restricción exclusiva.
OpenRouter conserva sus fallbacks normales si Cerebras no sirve el modelo elegido.

Este método utiliza LiteLLM y OpenRouter.

## Configuración

La clave API de OpenRouter (OPENROUTER_API_KEY) debe estar configurada en el archivo .env y cargada como variable de entorno.

Antes de usar este método, añade `litellm` al proyecto uv (pydantic ya llega como dependencia transitiva de `pydantic-settings`):

`uv add litellm`

## Fragmentos de código

Utiliza el código como estos ejemplos para usar OpenRouter con Cerebras como
proveedor preferido.

### Importaciones y constantes

```python
import litellm
from litellm import completion

from app.settings import Settings

settings = Settings()
MODEL = settings.openrouter_model
PROVIDER_ORDER = settings.openrouter_provider_order
EXTRA_BODY = {"provider": {"order": [PROVIDER_ORDER], "allow_fallbacks": True}}

# Algunos proveedores compatibles no aceptan parámetros opcionales como
# reasoning_effort. LiteLLM los descarta, pero response_format sigue siendo
# obligatorio para el flujo estructurado de la aplicación.
litellm.drop_params = True
```

`dots-studio/dots-3-note-preview:free` no se sirve actualmente mediante
Cerebras. Con esta configuración OpenRouter intentará Cerebras primero y caerá
en un proveedor compatible (AtlasCloud actualmente). No afirmar que una
petición de Dots fue procesada por Cerebras. Registra el proveedor devuelto por
OpenRouter para diagnóstico.

### Código para una respuesta de texto

```python
response = completion(model=MODEL, messages=messages, reasoning_effort="low", extra_body=EXTRA_BODY)
result = response.choices[0].message.content
```

### Código para una respuesta estructurada

```python
response = completion(model=MODEL, messages=messages, response_format=MyBaseModelSubclass, reasoning_effort="low", extra_body=EXTRA_BODY)
result = response.choices[0].message.content
result_as_object = MyBaseModelSubclass.model_validate_json(result)
```

Si `model_validate_json()` falla, no ejecutes efectos secundarios. Devuelve un
error controlado al cliente y registra el fallo sin incluir secretos.
